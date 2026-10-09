# ==============================================================================
# Script de Build para Windows (PyInstaller) — Radar Nacional de Licitações
# ==============================================================================

Write-Host "Iniciando processo de build do Radar Nacional de Licitações..." -ForegroundColor Cyan

# Diretório raiz do projeto
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# Verifica ambiente virtual
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "Ambiente virtual não encontrado em .venv! Abortando." -ForegroundColor Red
    exit 1
}

Write-Host "Usando Python: $PythonExe" -ForegroundColor Green

# Executa testes automatizados antes do empacotamento
Write-Host "Executando testes automatizados (pytest)..." -ForegroundColor Yellow
& $PythonExe -m pytest tests/ -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "Testes falharam! Build cancelado para preservar integridade." -ForegroundColor Red
    exit 1
}

Write-Host "Testes aprovados. Gerando executável com PyInstaller..." -ForegroundColor Green

# Executa PyInstaller para gerar executável standalone
# Opções:
# --noconsole: Executável com janela gráfica nativa (sem terminal para o usuário)
# --name: Nome do executável
# --clean: Limpa cache antes do build
# Evita capturar DLLs de runtimes externos (Poppler, Conda etc.) no PATH.
$RadarOriginalPath = $env:PATH
try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    & $PythonExe -m PyInstaller --noconfirm --clean --distpath dist_v1_1 --workpath build_v1_1 RadarNacionalLicitacoes.spec
    $RadarBuildExitCode = $LASTEXITCODE
} finally {
    $env:PATH = $RadarOriginalPath
}
if ($RadarBuildExitCode -ne 0) { exit $RadarBuildExitCode }

# Só aprovar o pacote após abrir e encerrar a janela em banco isolado.
& $PythonExe scripts/smoke_build.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Smoke test do executável falhou. Consulte scratch\packaged_smoke_result.json." -ForegroundColor Red
    exit 1
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "==================================================================" -ForegroundColor Green
    Write-Host "Build concluído com sucesso!" -ForegroundColor Green
    Write-Host "Executável gerado em: dist_v1_1\RadarNacionalLicitacoes\RadarNacionalLicitacoes.exe" -ForegroundColor Cyan
    Write-Host "==================================================================" -ForegroundColor Green
} else {
    Write-Host "Falha durante a compilação com PyInstaller." -ForegroundColor Red
    exit 1
}
