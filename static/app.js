const viewSelect = document.getElementById("view-select");
const viewProgress = document.getElementById("view-progress");
const viewResult = document.getElementById("view-result");
const statusText = document.getElementById("status-text");
const statusDetail = document.getElementById("status-detail");
const statusExplain = document.getElementById("status-explain");
const podInfo = document.getElementById("pod-info");
const podPhase = document.getElementById("pod-phase");
const podEvents = document.getElementById("pod-events");
const resultMeta = document.getElementById("result-meta");
const briefingContent = document.getElementById("briefing-content");

let pollTimer = null;

const STATUS_EXPLANATIONS = {
    queued: "Your request is in the queue. The worker will pick it up shortly.",
    scaling_gpu: "The AI model runs on a dedicated GPU node. When idle, the GPU pod scales to zero to save resources. It's now spinning back up and loading the model into GPU memory — this typically takes 1–2 minutes.",
    scoring: "Each article is being sent to the AI model to evaluate how relevant it is to your selected interests, scored from 1 to 10. The top-scoring articles will be selected for your briefing.",
    writing: "The highest-scored articles have been selected. The AI model is now synthesizing them into a concise newsletter briefing.",
};

function renderPodStatus(ps) {
    if (!ps) {
        podInfo.classList.add("hidden");
        return;
    }
    const parts = [ps.phase].filter(Boolean);
    if (ps.container_state) parts.push(ps.container_state);
    podPhase.textContent = parts.join(" · ");

    podEvents.innerHTML = "";
    (ps.events || []).forEach(ev => {
        const li = document.createElement("li");
        if (ev.type === "Warning") li.classList.add("warning");
        const ts = ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : "";
        li.textContent = ts ? `[${ts}] ${ev.reason}: ${ev.message}` : `${ev.reason}: ${ev.message}`;
        podEvents.appendChild(li);
    });

    podInfo.classList.remove("hidden");
}

function showView(view) {
    viewSelect.classList.add("hidden");
    viewProgress.classList.add("hidden");
    viewResult.classList.add("hidden");
    view.classList.remove("hidden");
}

function getSelectedInterests() {
    const checked = document.querySelectorAll('input[name="interest"]:checked');
    return Array.from(checked).map(cb => cb.value).join(", ");
}

async function loadCounts() {
    try {
        const resp = await fetch("/api/counts");
        const data = await resp.json();
        for (const [hours, count] of Object.entries(data.counts)) {
            const el = document.getElementById(`count-${hours}`);
            if (el) el.textContent = `${count} article${count !== 1 ? "s" : ""}`;
        }
    } catch (e) {
        console.error("Failed to load counts:", e);
    }
}

async function startDigest(hours) {
    const interests = getSelectedInterests();
    if (!interests) {
        alert("Please select at least one interest.");
        return;
    }

    showView(viewProgress);
    statusText.textContent = "Starting...";
    statusDetail.textContent = "";
    statusExplain.textContent = "";
    renderPodStatus(null);

    try {
        const resp = await fetch("/api/digest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ timeframe_hours: hours, interests: interests }),
        });
        const data = await resp.json();
        pollJob(data.job_id);
    } catch (e) {
        statusText.textContent = "Failed to start job";
        statusDetail.textContent = e.message;
    }
}

function pollJob(jobId) {
    if (pollTimer) clearInterval(pollTimer);

    const check = async () => {
        try {
            const resp = await fetch(`/api/jobs/${jobId}`);
            const job = await resp.json();

            const statusMap = {
                queued: "Queued...",
                scaling_gpu: "Scaling GPU...",
                scoring: "Scoring articles...",
                writing: "Writing briefing...",
                completed: "Done!",
                failed: "Failed",
            };

            statusText.textContent = statusMap[job.status] || job.status;
            statusDetail.textContent = job.progress || "";
            statusExplain.textContent = STATUS_EXPLANATIONS[job.status] || "";
            renderPodStatus(job.pod_status);

            if (job.status === "completed") {
                clearInterval(pollTimer);
                pollTimer = null;
                await showResult(jobId, job);
            } else if (job.status === "failed") {
                clearInterval(pollTimer);
                pollTimer = null;
                statusDetail.textContent = job.error || "An error occurred";
                statusExplain.textContent = "";
            }
        } catch (e) {
            console.error("Poll error:", e);
        }
    };

    check();
    pollTimer = setInterval(check, 5000);
}

async function showResult(jobId, job) {
    try {
        const resp = await fetch(`/api/digests/${jobId}`);
        const digest = await resp.json();

        let meta = "";
        if (digest.interests) {
            meta += `<div class="meta-row"><strong>Interests:</strong> ${digest.interests}</div>`;
        }
        if (digest.timeframe_hours) {
            const days = digest.timeframe_hours / 24;
            meta += `<div class="meta-row"><strong>Timeframe:</strong> Last ${days} day${days !== 1 ? "s" : ""}</div>`;
        }
        const scored = digest.total_scored || "?";
        meta += `<div class="meta-row"><strong>Articles:</strong> Top ${digest.article_count} selected from ${scored} scored</div>`;
        if (digest.processing_time_seconds) {
            const mins = Math.round(digest.processing_time_seconds / 60);
            meta += `<div class="meta-row"><strong>Processed in:</strong> ${mins > 0 ? mins + " min" : "< 1 min"}</div>`;
        }
        resultMeta.innerHTML = meta;
        briefingContent.innerHTML = digest.briefing;

        showView(viewResult);
    } catch (e) {
        statusText.textContent = "Failed to load digest";
        statusDetail.textContent = e.message;
    }
}

function reset() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
    showView(viewSelect);
    loadCounts();
}

// Event listeners
document.querySelectorAll(".card").forEach((card) => {
    card.addEventListener("click", () => {
        const hours = parseInt(card.dataset.hours);
        startDigest(hours);
    });
});

document.getElementById("btn-back-progress").addEventListener("click", reset);
document.getElementById("btn-back-result").addEventListener("click", reset);

// Initial load
loadCounts();
