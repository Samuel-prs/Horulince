# Executar no PowerShell: .\iniciar_iphone.ps1
param(
    [string]$Fonte = '',
    [string]$Placa = '',
    [string]$Tipo = 'carro',
    [string]$Cor = 'branco',
    [switch]$Testar,
    [switch]$SemOcr
)
$ErrorActionPreference = 'Stop'
$pythonHorulince = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonHorulince)) {
    throw 'Ambiente Python não encontrado. Siga a preparação do README.'
}
Push-Location -LiteralPath $PSScriptRoot
try {
    $argumentosHorulince = @('-m', 'horulince')
    if ($Testar) {
        $argumentosHorulince += @('testar-camera', '--mostrar')
    } else {
        $argumentosHorulince += @('iphone', '--mostrar', '--tipo', $Tipo, '--cor', $Cor)
        if ($Placa) { $argumentosHorulince += @('--placa', $Placa) }
        if ($SemOcr) { $argumentosHorulince += '--sem-ocr' }
    }
    if ($Fonte) { $argumentosHorulince += @('--fonte', $Fonte) }
    & $pythonHorulince @argumentosHorulince
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível concluir a conexão ou análise. Confira a mensagem acima.' }
} finally {
    Pop-Location
}
