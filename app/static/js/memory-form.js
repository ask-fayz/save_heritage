// Memory form: switches fields by kind and records voice in the browser with MediaRecorder.
(function () {
  "use strict";

  const form = document.querySelector("[data-memory-form]");
  if (!form) return;

  const realFile = form.querySelector("[data-real-file]");
  const textLabel = form.querySelector("[data-text-label]");
  const textArea = form.querySelector("textarea[name=text]");
  const recordButton = form.querySelector("[data-record]");
  const recordStatus = form.querySelector("[data-record-status]");
  const preview = form.querySelector("[data-record-preview]");
  const MAX_SECONDS = 300;

  const kind = () => form.querySelector("input[name=kind]:checked").value;

  function setRealFile(file) {
    const transfer = new DataTransfer();
    if (file) transfer.items.add(file);
    realFile.files = transfer.files;
  }

  function update() {
    const current = kind();
    form.querySelectorAll("[data-for]").forEach((el) => { el.hidden = el.dataset.for !== current; });
    textLabel.textContent = { story: "Your story", photo: "What is in the photo? (optional)", audio: "Anything to add? (optional)" }[current];
    textArea.required = current === "story";
    setRealFile(null);
    const picker = form.querySelector(`[data-file="${current}"]`);
    if (picker && picker.files[0]) setRealFile(picker.files[0]);
  }

  form.querySelectorAll("input[name=kind]").forEach((input) => input.addEventListener("change", update));
  form.querySelectorAll("[data-file]").forEach((picker) => {
    picker.addEventListener("change", () => {
      if (picker.dataset.file === kind()) setRealFile(picker.files[0] || null);
    });
  });

  form.addEventListener("submit", (event) => {
    if (kind() !== "story" && !realFile.files.length) {
      event.preventDefault();
      alert(kind() === "photo" ? "Please choose a photo." : "Please record or choose an audio file.");
    }
  });

  // ---------------------------------------------------------------- recording
  let recorder = null;
  let timer = null;

  function pickMime() {
    const candidates = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4", "audio/webm"];
    return candidates.find((type) => window.MediaRecorder && MediaRecorder.isTypeSupported(type)) || "";
  }

  if (!navigator.mediaDevices || !window.MediaRecorder) {
    recordButton.disabled = true;
    recordStatus.textContent = "Recording is not supported in this browser. Upload a file instead.";
  }

  recordButton.addEventListener("click", async () => {
    if (recorder && recorder.state === "recording") {
      recorder.stop();
      return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      recordStatus.textContent = "Microphone access was blocked. You can upload a file instead.";
      return;
    }
    const mimeType = pickMime();
    const chunks = [];
    recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    recorder.addEventListener("dataavailable", (e) => e.data.size && chunks.push(e.data));
    recorder.addEventListener("stop", () => {
      clearInterval(timer);
      stream.getTracks().forEach((track) => track.stop());
      const type = (recorder.mimeType || "audio/webm").split(";")[0];
      const ext = { "audio/ogg": "ogg", "audio/mp4": "m4a" }[type] || "webm";
      const blob = new Blob(chunks, { type });
      setRealFile(new File([blob], `voice.${ext}`, { type }));
      preview.src = URL.createObjectURL(blob);
      preview.hidden = false;
      recordButton.textContent = "● Record again";
      recordStatus.textContent = "Recording ready. Listen, then send it for review.";
    });
    recorder.start();
    const started = Date.now();
    recordButton.textContent = "■ Stop";
    timer = setInterval(() => {
      const seconds = Math.round((Date.now() - started) / 1000);
      recordStatus.textContent = `Recording… ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
      if (seconds >= MAX_SECONDS) recorder.stop();
    }, 500);
  });

  update();
})();
