// Polls a background job and renders its progress steps.
(function () {
  const job = window.SAVE_JOB;
  if (!job || job.status === "done" || job.status === "failed") return;

  const stepsEl = document.getElementById("job-steps");
  const titleEl = document.getElementById("job-title");
  const errorEl = document.getElementById("job-error");
  const doneEl = document.getElementById("job-done");
  const linkEl = document.getElementById("job-link");
  const hintEl = document.getElementById("job-hint");

  function renderSteps(steps) {
    stepsEl.replaceChildren(...steps.map((step) => {
      const li = document.createElement("li");
      li.className = step.state;
      const icon = document.createElement("span");
      icon.className = "icon";
      icon.setAttribute("aria-hidden", "true");
      icon.textContent = { done: "✓", warning: "!", failed: "×" }[step.state] || "";
      const body = document.createElement("div");
      const label = document.createElement("div");
      label.textContent = step.label;
      body.append(label);
      if (step.note) {
        const note = document.createElement("div");
        note.className = "note";
        note.textContent = step.note;
        body.append(note);
      }
      li.append(icon, body);
      return li;
    }));
  }

  async function poll() {
    try {
      const response = await fetch(`/api/jobs/${job.id}`, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(response.statusText);
      const data = await response.json();
      renderSteps(data.steps || []);
      if (data.status === "done") {
        titleEl.textContent = job.done;
        hintEl.hidden = true;
        doneEl.hidden = false;
        if (data.result && data.result.site_slug) {
          linkEl.href = `/site/${encodeURIComponent(data.result.site_slug)}${data.result.story ? "/story" : ""}?lang=${job.lang}`;
          if ((job.kind === "generate" || job.kind === "story")) setTimeout(() => { window.location.href = linkEl.href; }, 1200);
        }
        return;
      }
      if (data.status === "failed") {
        titleEl.textContent = job.failed;
        hintEl.hidden = true;
        errorEl.hidden = false;
        errorEl.textContent = data.error || "The task failed.";
        return;
      }
    } catch (err) {
      console.warn("Job polling failed", err);
    }
    setTimeout(poll, 1500);
  }
  poll();
})();
