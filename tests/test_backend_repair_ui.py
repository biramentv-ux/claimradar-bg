from pathlib import Path


def test_electron_backend_repair_controls_exist():
    main = Path('desktop/electron/main.js').read_text(encoding='utf-8')
    preload = Path('desktop/electron/preload.js').read_text(encoding='utf-8')
    html = Path('desktop/electron/renderer/index.html').read_text(encoding='utf-8')
    renderer = Path('desktop/electron/renderer/renderer.js').read_text(encoding='utf-8')
    assert 'backendDiagnostics' in main
    assert 'backendCandidates' in main
    assert 'claimradar:start-backend' in preload
    assert 'Стартирай backend' in html
    assert 'checkNow' in renderer
    assert 'startBackend' in renderer


def test_backend_launcher_reports_logs_and_plan():
    main = Path('desktop/electron/main.js').read_text(encoding='utf-8')
    assert 'backendLogs' in main
    assert 'backendLaunchPlan' in main
    assert 'api/local-ai/status' in main
