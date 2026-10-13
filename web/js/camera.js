// Live camera with an on-screen guide square. Falls back to the phone's own
// camera app (<input capture>) or the gallery when this isn't possible.

export class CameraError extends Error {
  constructor(code) {
    super(code);
    this.code = code; // "denied" | "unavailable"
  }
}

let stream = null;

export async function startCamera(video) {
  if (!navigator.mediaDevices?.getUserMedia || !window.isSecureContext) throw new CameraError("unavailable");
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1920 } },
    });
  } catch (err) {
    throw new CameraError(err?.name === "NotAllowedError" || err?.name === "SecurityError" ? "denied" : "unavailable");
  }
  video.srcObject = stream;
  await video.play().catch(() => {});
  if (!video.videoWidth) await new Promise((resolve) => video.addEventListener("loadedmetadata", resolve, { once: true }));
}

export function stopCamera(video) {
  stream?.getTracks().forEach((track) => track.stop());
  stream = null;
  if (video) video.srcObject = null;
}

// Grab the current frame, and work out where the on-screen guide square sits in
// the frame's own pixels (the video is shown with object-fit: cover).
export async function captureFrame(video, guide) {
  const vw = video.videoWidth, vh = video.videoHeight;
  const box = video.getBoundingClientRect();
  const g = guide.getBoundingClientRect();
  const scale = Math.max(box.width / vw, box.height / vh);
  const offsetX = (box.width - vw * scale) / 2;
  const offsetY = (box.height - vh * scale) / 2;
  const cx = (g.left + g.width / 2 - box.left - offsetX) / scale;
  const cy = (g.top + g.height / 2 - box.top - offsetY) / scale;
  const side = g.width / scale;

  const canvas = document.createElement("canvas");
  canvas.width = vw;
  canvas.height = vh;
  canvas.getContext("2d").drawImage(video, 0, 0, vw, vh);
  const bitmap = await createImageBitmap(canvas);
  canvas.width = canvas.height = 0; // free the copy
  return { bitmap, cx, cy, side };
}
