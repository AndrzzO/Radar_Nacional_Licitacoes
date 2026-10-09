"""Smoke test isolado e limitado a 30 s do pacote Windows."""
import os,sys,subprocess,json,hashlib
from pathlib import Path
from datetime import datetime
root=Path(__file__).resolve().parents[1]
exe=root/'dist_v1_1'/'RadarNacionalLicitacoes'/'RadarNacionalLicitacoes.exe'
dest=root/'scratch'/('packaged_smoke_'+datetime.now().strftime('%Y%m%d_%H%M%S')); dest.mkdir(parents=True)
env={**os.environ,'RADAR_DATA_DIR':str(dest),'QT_QPA_PLATFORM':'offscreen'}
# O pacote também deve respeitar uma instância já em execução, sem iniciar
# banco, logger ou interface. A trava é a mesma usada no ponto de entrada.
sys.path.insert(0, str(root))
from src.utils.single_instance import SingleInstance
guard = SingleInstance()
if not guard.acquired:
    raise SystemExit("Feche o Radar aberto antes de validar o novo pacote.")
try:
    duplicates = [subprocess.Popen([str(exe), '--smoke-test'], cwd=root, env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        for _ in range(3)]
    for duplicate in duplicates:
        try:
            assert duplicate.wait(timeout=30) == 0
        except subprocess.TimeoutExpired:
            duplicate.terminate()
            duplicate.wait(timeout=10)
            raise
    assert not (dest / 'logs').exists(), "Segunda instância iniciou o logger"
    assert not list(dest.glob('*.sqlite3')), "Segunda instância acessou o banco"
finally:
    guard.close()
print('SINGLE_INSTANCE_OK: três aberturas simultâneas bloqueadas')
process=subprocess.Popen([str(exe),'--smoke-test'],cwd=root,env=env,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
timeout=False
try: code=process.wait(timeout=30)
except subprocess.TimeoutExpired:
    timeout=True; process.terminate(); code=process.wait(timeout=10)
log=(dest/'logs'/'radar.log').read_text(encoding='utf8') if (dest/'logs'/'radar.log').exists() else ''
startup=(dest/'startup_error.log').read_text(encoding='utf8') if (dest/'startup_error.log').exists() else ''
result=dict(executable=str(exe),sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),data_dir=str(dest),exit_code=code,timeout=timeout,success=code==0 and 'SMOKE_TEST_OK' in log and 'COURSE_SMOKE_OK' in log,log=log,startup_error=startup)
(root/'scratch'/'packaged_smoke_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2)); sys.exit(0 if result['success'] else 1)
