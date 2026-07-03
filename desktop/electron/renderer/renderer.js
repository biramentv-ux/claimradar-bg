async function refreshStatus() {
  const box = document.getElementById('status');
  try {
    const status = await window.claimRadarDesktop.localStatus();
    box.textContent = JSON.stringify(status, null, 2);
  } catch (error) {
    box.textContent = String(error);
  }
}
refreshStatus();
setInterval(refreshStatus, 3000);
