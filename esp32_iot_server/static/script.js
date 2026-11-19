/**
 * ==============================================================================
 * Transformer Energy Monitoring System - Client Script (script.js)
 * ==============================================================================
 * Polls /api/data every 2 seconds.
 * - Displays all houses in kWh (IN1 marked as LIVE ESP32 with blink counts).
 * - Tracks Transformer Total Input (30.0 kWh) vs Total Energy Consumed by houses.
 * ==============================================================================
 */

// Header status elements
const systemStatusBadge = document.getElementById("system-status-badge");
const systemLastSync = document.getElementById("system-last-sync");

// Block 1 Elements (House Energy Details in kWh)
const activeHousesCount = document.getElementById("active-houses-count");
const housesContainer = document.getElementById("houses-container");
const valRunningTotal = document.getElementById("val-running-total");

// Block 2 Elements (Transformer Details in kWh)
const valTransformerIdBadge = document.getElementById("val-transformer-id-badge");
const valTcCount = document.getElementById("val-tc-count");
const valDtOutput = document.getElementById("val-dt-output");
const valLoadDetails = document.getElementById("val-load-details");
const valTfCapacity = document.getElementById("val-tf-capacity");
const valLoadVsCapacityText = document.getElementById("val-load-vs-capacity-text");
const valLoadPctBadge = document.getElementById("val-load-pct-badge");
const capacityProgressFill = document.getElementById("capacity-progress-fill");

/**
 * Natural sort helper for house IDs: IN1, IN2, IN3, etc.
 */
function sortHouseIds(ids) {
    return ids.sort((a, b) => a.localeCompare(undefined, undefined, { numeric: true, sensitivity: 'base' }));
}

/**
 * Updates the overall system status badge.
 */
function setSystemStatus(text, statusClass) {
    systemStatusBadge.textContent = text;
    systemStatusBadge.className = `status-badge status-${statusClass}`;
}

/**
 * Renders individual house load cards in Block 1.
 */
function renderHouses(houses) {
    const houseKeys = Object.keys(houses || {});

    if (houseKeys.length === 0) {
        housesContainer.innerHTML = `
            <div class="house-card house-card-waiting">
                <div class="house-info-left">
                    <span class="house-id-title">Waiting for house data...</span>
                    <span class="house-timestamp">Send POST from ESP32 to populate</span>
                </div>
                <div class="house-load-right">
                    <span class="stat-number">--</span>
                    <span class="stat-unit">kWh</span>
                </div>
            </div>
        `;
        activeHousesCount.textContent = "0 houses";
        return;
    }

    activeHousesCount.textContent = `${houseKeys.length} houses`;
    const sortedKeys = sortHouseIds(houseKeys);

    // Map existing cards in DOM
    const existingCardsMap = new Map();
    housesContainer.querySelectorAll(".house-card").forEach(card => {
        if (card.dataset.houseId) {
            existingCardsMap.set(card.dataset.houseId, card);
        }
    });

    sortedKeys.forEach(houseId => {
        const house = houses[houseId];
        const isLiveNode = house.is_live === true || houseId === "IN1";
        const isWaiting = house.status === "WAITING";

        const loadVal = (house.load_kwh !== null && house.load_kwh !== undefined)
            ? Number(house.load_kwh).toFixed(3)
            : "--";

        // Calculate or retrieve blink count (3200 blinks = 1 kWh)
        const blinksCount = (house.blink_count !== undefined && house.blink_count !== null)
            ? Number(house.blink_count)
            : Math.round(Number(house.load_kwh || 0) * 3200);

        const blinksFormatted = blinksCount.toLocaleString();
        const blinksHtml = `<span class="blink-bulb">&#x1F4A1;</span> <span class="blink-num">${blinksFormatted}</span> <span class="blink-label">blinks</span>`;

        const timeVal = house.last_updated ? house.last_updated : "Active";
        const startVal = house.start_time ? house.start_time : (isWaiting ? "--" : "Active");

        const badgeHtml = isLiveNode
            ? (isWaiting ? `<span class="tag-live" style="color: #f59e0b; border-color: rgba(245,158,11,0.4);">ESP32 (WAITING)</span>` : `<span class="tag-live">LIVE ESP32</span>`)
            : `<span class="tag-sim">SIMULATED</span>`;

        const timeMetaHtml = `
            <span class="house-start-time" title="Session started at">&#x23F1; Started: <strong>${startVal}</strong></span>
            <span class="house-time-sep">&bull;</span>
            <span class="house-timestamp" title="Last update timestamp">${timeVal}</span>
        `;

        if (existingCardsMap.has(houseId)) {
            // Update existing card DOM in place
            const card = existingCardsMap.get(houseId);
            card.className = `house-card ${isWaiting ? 'house-card-waiting' : ''}`;
            card.querySelector(".stat-number").textContent = loadVal;

            const timeMetaElem = card.querySelector(".house-time-meta");
            if (timeMetaElem) {
                timeMetaElem.innerHTML = timeMetaHtml;
            } else {
                const oldTs = card.querySelector(".house-timestamp");
                if (oldTs) oldTs.outerHTML = `<div class="house-time-meta">${timeMetaHtml}</div>`;
            }

            const titleElem = card.querySelector(".house-id-title");
            if (titleElem) {
                titleElem.innerHTML = `${houseId} ${badgeHtml}`;
            }

            let blinksElem = card.querySelector(".house-blinks");
            if (blinksElem) {
                blinksElem.innerHTML = blinksHtml;
            } else {
                const infoLeft = card.querySelector(".house-info-left");
                if (infoLeft) {
                    const row = document.createElement("div");
                    row.className = "house-blinks-row";
                    row.innerHTML = `
                        <div class="house-blinks">${blinksHtml}</div>
                        <button class="btn-restart-counter" title="Restart count from 0" onclick="restartHouseCounter('${houseId}', event)">
                            <span class="btn-restart-icon">&#x21BB;</span> Restart
                        </button>
                    `;
                    infoLeft.appendChild(row);
                }
            }
            existingCardsMap.delete(houseId);
        } else {
            // Create a new card
            const newCard = document.createElement("div");
            newCard.className = `house-card ${isWaiting ? 'house-card-waiting' : ''}`;
            newCard.dataset.houseId = houseId;
            newCard.innerHTML = `
                <div class="house-info-left">
                    <span class="house-id-title">
                        ${houseId}
                        ${badgeHtml}
                    </span>
                    <div class="house-time-meta">${timeMetaHtml}</div>
                    <div class="house-blinks-row">
                        <div class="house-blinks">${blinksHtml}</div>
                        <button class="btn-restart-counter" title="Restart count from 0" onclick="restartHouseCounter('${houseId}', event)">
                            <span class="btn-restart-icon">&#x21BB;</span> Restart
                        </button>
                    </div>
                </div>
                <div class="house-load-right">
                    <span class="stat-number">${loadVal}</span>
                    <span class="stat-unit">kWh</span>
                </div>
            `;
            housesContainer.appendChild(newCard);
        }
    });

    // Remove any cards no longer in data
    existingCardsMap.forEach(card => card.remove());
}

/**
 * Updates Transformer metrics in Block 2 (All in kWh).
 */
function renderTransformer(tf, sumHouseKwh) {
    const totalInputKwh = (tf && tf.total_input_kwh) ? Number(tf.total_input_kwh) : 30.0;
    const totalConsumedKwh = Number(sumHouseKwh || (tf && tf.total_consumed_kwh) || 0);

    // Transformer ID & TC Count
    valTransformerIdBadge.textContent = (tf && tf.transformer_id) ? tf.transformer_id : "TC1";
    valTcCount.textContent = (tf && tf.tc_count) ? tf.tc_count : 1;

    // DT Total Input (30.0 kWh)
    valDtOutput.textContent = totalInputKwh.toFixed(1);
    valTfCapacity.textContent = totalInputKwh.toFixed(1);

    // Total Consumed
    valLoadDetails.textContent = totalConsumedKwh.toFixed(2);

    // Load vs Capacity Utilization (Consumed vs 30.0 kWh Input)
    const pctUsed = ((totalConsumedKwh / totalInputKwh) * 100);
    valLoadVsCapacityText.textContent = `${totalConsumedKwh.toFixed(2)} / ${totalInputKwh.toFixed(1)} kWh used`;
    valLoadPctBadge.textContent = `${pctUsed.toFixed(1)}% used`;

    const clampedPct = Math.min(Math.max(pctUsed, 0), 100);
    capacityProgressFill.style.width = `${clampedPct}%`;

    // Visual color codes based on threshold
    capacityProgressFill.classList.remove("warn", "overload");
    valLoadPctBadge.classList.remove("warn", "overload");

    if (pctUsed > 100) {
        capacityProgressFill.classList.add("overload");
        valLoadPctBadge.classList.add("overload");
    } else if (pctUsed >= 80) {
        capacityProgressFill.classList.add("warn");
        valLoadPctBadge.classList.add("warn");
    }
}

/**
 * Main polling routine: fetches /api/data and triggers UI updates.
 */
async function fetchMonitoringData() {
    try {
        const response = await fetch("/api/data");

        if (!response.ok) {
            throw new Error(`Server returned HTTP ${response.status}`);
        }

        const data = await response.json();

        // ---------------------------------------------------------------------
        // Check Live ESP32 status
        // ---------------------------------------------------------------------
        const isEsp32Online = data.houses && data.houses["IN1"] && data.houses["IN1"].status === "ONLINE";

        if (isEsp32Online) {
            setSystemStatus("ESP32 ONLINE", "online");
            systemLastSync.textContent = `ESP32 Active: ${data.houses["IN1"].last_updated || "Live"}`;
        } else {
            setSystemStatus("WAITING FOR ESP32", "waiting");
            systemLastSync.textContent = "Listening on /api/data for ESP32 packet...";
        }

        // 1. Render Block 1: Houses (kWh)
        const houses = data.houses || {};
        renderHouses(houses);

        // 2. Update Running Total (Σ) Card in Block 1
        const totalKwh = Number(data.sum_house_kwh || 0);
        valRunningTotal.textContent = totalKwh.toFixed(2);

        // 3. Render Block 2: Transformer Details (30.0 kWh Input vs Consumed)
        renderTransformer(data.transformer, totalKwh);

    } catch (error) {
        console.warn("Telemetry fetch error:", error);
        setSystemStatus("SERVER OFFLINE", "offline");
        systemLastSync.textContent = "Lost connection to Flask server";
    }
}

/**
 * Sends a restart request to reset a house's blink counter to 0.
 */
window.restartHouseCounter = async function(houseId, event) {
    if (event) {
        event.stopPropagation();
        const btn = event.currentTarget;
        btn.classList.add("btn-spinning");
    }

    try {
        const response = await fetch("/api/reset", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ house_id: houseId })
        });

        if (response.ok) {
            await fetchMonitoringData();
        } else {
            console.error("Reset returned error:", response.status);
        }
    } catch (err) {
        console.error("Failed to reset counter:", err);
    } finally {
        if (event && event.currentTarget) {
            setTimeout(() => {
                event.currentTarget.classList.remove("btn-spinning");
            }, 600);
        }
    }
};

// -----------------------------------------------------------------------------
// Initialize and poll every 2000 ms (2 seconds)
// -----------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    fetchMonitoringData();
    setInterval(fetchMonitoringData, 2000);
});
