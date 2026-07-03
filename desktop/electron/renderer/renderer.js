async function checkNow() {
  const box = document.getElementById('status');
  try {
    const diag = await window.claimRadarDesktop.backendDiagnostics();
    box.textContent = JSON.stringify(diag, null, 2);
    if (diag.ok) {
      window.location.href = 'http://127.0.0.1:8765/desktop';
    }
  } catch (error) {
    box.textContent = String(error);
  }
}

async function startBackend() {
  const box = document.getElementById('status');
  box.textContent = 'Стартирам backend-а...';
  try {
    const started = await window.claimRadarDesktop.startBackend();
    box.textContent = JSON.stringify(started, null, 2);
    setTimeout(checkNow, 2500);
  } catch (error) {
    box.textContent = String(error);
  }
}

async function openDesktop() {
  await window.claimRadarDesktop.openDesktop();
}

checkNow();
setInterval(checkNow, 5000);
