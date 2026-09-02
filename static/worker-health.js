async function updateWorkerHealth() {
    const element = document.getElementById('workerHealth');
    if (!element) return;
    try {
        const response = await fetch('/new-portfolio/worker_status');
        const payload = await response.json();
        if (!response.ok || !payload.success) throw new Error();
        const data = payload.data;
        const success = data.last_success ? new Date(data.last_success).toLocaleString() : 'not yet recorded';
        const attempt = data.last_attempt ? new Date(data.last_attempt).toLocaleString() : 'none';
        const issue = !data.configured || data.overdue || data.last_error;
        element.className = issue ? 'alert alert-warning' : 'alert alert-success';
        element.textContent = `Automatic history: last success ${success}; last attempt ${attempt}. Scheduled every ${data.interval_seconds / 60} minutes.`;
        if (!data.configured) element.textContent += ' Configure the same dedicated WORKER_KEY on the web and worker services.';
        else if (data.overdue) element.textContent += ' Updates are overdue; check the Railway worker.';
        if (data.last_error) element.textContent += ` Last error: ${data.last_error}`;
    } catch (_) {
        element.className = 'alert alert-warning';
        element.textContent = 'Automatic history status is unavailable. Check Railway service health.';
    }
}
