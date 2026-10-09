"""Coleta incremental com diagnóstico explícito de partições incompletas."""
from datetime import timedelta
from itertools import product
from src.domain.modalities import MODALITIES
from src.database.repositories import ProcurementRepository, SyncRepository
from src.domain.entities import Sincronizacao
from src.integrations.pncp_client import PNCPClient, PNCPClientError
from src.integrations.pncp_adapter import PNCPAdapter
from src.utils.datetime_utils import get_current_time_sp, format_date_api, parse_datetime
from src.utils.logging_config import get_logger

logger=get_logger()
MAX_PAGES_SAFETY_LIMIT=500


class CollectionService:
    def __init__(self,procurement_repo,sync_repo,pncp_client=None):
        self.repo=procurement_repo; self.sync_repo=sync_repo
        self.client=pncp_client or PNCPClient()

    def run_collection(self,filtros,on_progress=None,is_cancelled=None,max_pages_per_partition=MAX_PAGES_SAFETY_LIMIT,collection_mode=None):
        cancelled=is_cancelled or (lambda:False)
        current=get_current_time_sp()
        sync=Sincronizacao(data_inicio=current.isoformat(),filtros_json=filtros.to_json())
        sync.id=self.sync_repo.create_sync(sync)
        errors=[]; received=new=updated=pages=requests=duplicates=0
        seen=set()
        initial_requests=getattr(self.client,"request_count",None)
        note=''
        try:
            open_mode=filtros.status_proposta=='recebendo_proposta' and collection_mode!='updates'
            ufs=filtros.ufs or [None]
            modalities=(filtros.modalidades_ids or [None]) if open_mode else (filtros.modalidades_ids or list(MODALITIES))
            end=parse_datetime(filtros.data_encerramento_fim) if filtros.data_encerramento_fim else current+timedelta(days=filtros.prazo_dias or 90)
            pub_start=parse_datetime(filtros.data_publicacao_inicio) if filtros.data_publicacao_inicio else current-timedelta(days=30)
            pub_end=parse_datetime(filtros.data_publicacao_fim) if filtros.data_publicacao_fim else current
            if not end or not pub_start or not pub_end or pub_start>pub_end: raise ValueError('Período de datas inválido.')
            note='Propostas: horizonte de encerramento '+end.strftime('%d/%m/%Y') if open_mode else 'Publicações: '+pub_start.strftime('%d/%m/%Y')+' a '+pub_end.strftime('%d/%m/%Y')
            if collection_mode=='updates': note=note.replace('Publicações:', 'Atualizações oficiais:')
            windows=[]
            if open_mode: windows=[(None,None)]
            else:
                start=pub_start
                while start.date()<=pub_end.date():
                    finish=min(start+timedelta(days=29),pub_end)
                    windows.append((start,finish)); start=finish+timedelta(days=1)
            partitions=list(product(ufs,modalities,windows))
            for uf,mod,window in partitions:
                if cancelled(): break
                page=1; total_pages=1; signatures=set(); partition_received=0
                while page<=total_pages:
                    if cancelled(): break
                    if page>max_pages_per_partition:
                        errors.append(f'{uf or "Brasil"}: limite de segurança atingido; coleta incompleta.'); break
                    try:
                        args=dict(uf=uf,modalidade_id=mod,codigo_ibge=filtros.municipios_ibge[0] if len(filtros.municipios_ibge)==1 else None,pagina=page,tamanho_pagina=50,check_cancelled=cancelled)
                        requests+=1
                        if open_mode: response=self.client.get_propostas(data_final=format_date_api(end),**args)
                        else:
                            method=self.client.get_atualizacoes if collection_mode=='updates' else self.client.get_publicacoes
                            response=method(data_inicial=format_date_api(window[0]),data_final=format_date_api(window[1]),**args)
                        if not isinstance(response,dict) or not isinstance(response.get('data'),list): raise PNCPClientError('Estrutura de resposta inválida; não equivale a zero resultados.')
                        raw=response['data']
                        if response.get('numeroPagina',page)!=page: raise PNCPClientError('Número de página fora da sequência.')
                        reported=response.get('totalPaginas')
                        if reported is not None:
                            if type(reported) is not int or reported<0: raise PNCPClientError('Total de páginas inválido.')
                            total_pages=max(reported,1)
                        else: total_pages=page+1 if raw else page
                        if not raw:
                            if page<total_pages or (page==1 and response.get('totalRegistros',0)>0): raise PNCPClientError('Página vazia antes do fim anunciado.')
                            break
                        signature=tuple(sorted(str(x.get('numeroControlePNCP')) for x in raw if isinstance(x,dict)))
                        if signature in signatures: raise PNCPClientError('Página repetida; coleta interrompida para evitar loop.')
                        signatures.add(signature)
                        batch=[]; received+=len(raw); partition_received+=len(raw)
                        for item in raw:
                            try:
                                lic=PNCPAdapter.parse_licitacao(item)
                                if not lic.numero_controle_pncp: raise ValueError('Identificador PNCP ausente')
                                if lic.numero_controle_pncp in seen:
                                    duplicates+=1; continue
                                seen.add(lic.numero_controle_pncp)
                                # Restrições confiáveis da fonte. Texto/categoria são filtros locais posteriores.
                                if filtros.ufs and lic.uf_sigla not in filtros.ufs: continue
                                if filtros.municipios_ibge and lic.municipio_ibge not in filtros.municipios_ibge: continue
                                if filtros.esferas and lic.esfera_id not in filtros.esferas: continue
                                if filtros.modalidades_ids and lic.modalidade_id not in filtros.modalidades_ids: continue
                                batch.append(lic)
                            except (ValueError,TypeError,AttributeError) as e:
                                errors.append(f'Página {page}: registro inválido: {e}')
                        n,u=self.repo.upsert_batch(batch); new+=n; updated+=u; pages+=1
                        if on_progress: on_progress(f'{note} — {uf or "Brasil"}, modalidade {mod or "todas"}, página {page}/{total_pages}',page,total_pages,received,new,updated)
                        if reported is not None and page==total_pages and response.get('totalRegistros') is not None and partition_received!=response['totalRegistros']:
                            errors.append(f'{uf or "Brasil"}: total recebido difere do anunciado ({partition_received}/{response["totalRegistros"]}); a fonte pode ter mudado durante a coleta.')
                        page+=1
                    except PNCPClientError as e:
                        if not cancelled(): errors.append(f'{uf or "Brasil"}, página {page}: {e}')
                        break
            status='Interrompida' if cancelled() else 'Falhou' if errors and not pages else 'Concluída com ressalvas' if errors else 'Concluída'
        except Exception as e:
            logger.exception('Falha de coleta'); errors.append(str(e)); status='Falhou'
        message=f'{status}: {new} novos, {updated} atualizados. {note}'
        sync.data_fim=get_current_time_sp().isoformat(); sync.status=status
        sync.total_recebidos=received; sync.novos=new; sync.atualizados=updated
        actual_requests=getattr(self.client,"request_count",None)
        if type(initial_requests) is int and type(actual_requests) is int: requests=actual_requests-initial_requests
        sync.total_requisicoes=requests; sync.paginas_concluidas=pages
        sync.descartados_duplicidade=duplicates; sync.erros='\n'.join(errors) or None
        self.sync_repo.update_sync(sync)
        if on_progress: on_progress(message,pages,pages,received,new,updated)
        return dict(sync_id=sync.id,status=status,total_recebidos=received,novos=new,atualizados=updated,paginas=pages,requisicoes=requests,erros=errors,mensagem=message)
