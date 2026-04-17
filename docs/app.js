// MN Lorcana Leaderboard — Client-side rendering

let leaderboardData = null;
let currentSort = { key: "rank", dir: "asc" };
let showUnranked = false;
let mode = "all"; // "all" or "sc"

async function loadData() {
    try {
        const resp = await fetch("data/leaderboard.json");
        leaderboardData = await resp.json();
        renderStats();
        renderTable();
        setupControls();
    } catch (e) {
        document.getElementById("leaderboard-body").innerHTML =
            '<tr><td colspan="7">Failed to load data. Check back later.</td></tr>';
    }
}

function renderStats() {
    const d = leaderboardData;
    document.getElementById("last-updated").textContent = formatDate(d.last_updated);
    document.getElementById("total-players").textContent = d.total_players;
    document.getElementById("total-matches").textContent = d.total_matches_processed;
    document.getElementById("min-matches").textContent = d.min_matches_for_ranking;
    updateStatsBar();
}

function updateStatsBar() {
    const d = leaderboardData;
    const ranked = mode === "sc" ? d.sc_ranked_players : d.ranked_players;
    const unranked = d.total_players - ranked;
    const bar = document.getElementById("stats-bar");
    bar.innerHTML = `
        <span><strong>${ranked}</strong> ranked players</span>
        <span><strong>${unranked}</strong> unranked</span>
        <span><strong>${d.total_matches_processed}</strong> matches processed</span>
    `;
}

function getTrack(player) {
    return player[mode] || player["all"];
}

function getRank(player) {
    return player[`${mode}_rank`] ?? player["all_rank"] ?? "—";
}

function getPlayers() {
    const ranked = (leaderboardData.ranked || []);
    if (showUnranked) {
        return [...ranked, ...(leaderboardData.unranked || [])];
    }
    return ranked;
}

function renderTable() {
    const search = (document.getElementById("search").value || "").toLowerCase();
    let players = getPlayers();

    // For set-champ mode, only show players who have SC matches (unless showing unranked)
    if (mode === "sc" && !showUnranked) {
        players = players.filter(p => p.sc.total_matches >= leaderboardData.min_matches_for_ranking);
    }

    if (search) {
        players = players.filter(p => p.name.toLowerCase().includes(search));
    }

    players = sortPlayers(players, currentSort.key, currentSort.dir);

    const tbody = document.getElementById("leaderboard-body");
    if (players.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7">No players found.</td></tr>';
        return;
    }

    tbody.innerHTML = players.map(p => {
        const t = getTrack(p);
        const rank = getRank(p);
        const streakText = formatStreak(t.current_streak, t.best_win_streak);
        const rankClass = typeof rank === "number" && rank <= 3 ? ` class="rank-${rank}"` : "";
        return `<tr${rankClass}>
            <td>${rank}</td>
            <td><span class="player-name" data-id="${p.player_id}">${escapeHtml(p.name)}</span></td>
            <td class="username-cell">${escapeHtml(p.username || "")}</td>
            <td>${t.elo.toFixed(0)}</td>
            <td>${t.record}</td>
            <td>${t.win_rate.toFixed(1)}%</td>
            <td>${streakText}</td>
            <td>${t.total_events}</td>
        </tr>`;
    }).join("");

    tbody.querySelectorAll(".player-name").forEach(el => {
        el.addEventListener("click", () => showPlayerDetail(parseInt(el.dataset.id)));
    });
}

function sortPlayers(players, key, dir) {
    const mult = dir === "asc" ? 1 : -1;
    return [...players].sort((a, b) => {
        const ta = getTrack(a), tb = getTrack(b);
        let va, vb;

        if (key === "rank") {
            va = getRank(a); vb = getRank(b);
            if (va === "—") va = 99999;
            if (vb === "—") vb = 99999;
        } else if (key === "name") {
            return mult * a.name.localeCompare(b.name);
        } else if (key === "username") {
            return mult * (a.username || "").localeCompare(b.username || "");
        } else if (key === "record") {
            va = ta.wins; vb = tb.wins;
        } else if (key === "elo") {
            va = ta.elo; vb = tb.elo;
        } else if (key === "win_rate") {
            va = ta.win_rate; vb = tb.win_rate;
        } else if (key === "current_streak") {
            va = ta.current_streak; vb = tb.current_streak;
        } else if (key === "total_events") {
            va = ta.total_events; vb = tb.total_events;
        } else {
            va = ta[key] ?? 0; vb = tb[key] ?? 0;
        }

        return mult * (va - vb);
    });
}

function formatStreak(current, best) {
    if (current === 0) return "0";
    if (current > 0) {
        const max = best > current ? ` (Max ${best})` : "";
        return `<span class="streak-win">W${current}${max}</span>`;
    }
    return `<span class="streak-loss">L${Math.abs(current)}</span>`;
}

function formatDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function setupControls() {
    document.getElementById("search").addEventListener("input", () => renderTable());

    document.getElementById("toggle-unranked").addEventListener("change", (e) => {
        showUnranked = e.target.checked;
        renderTable();
    });

    // Mode toggle (all / set champs)
    document.getElementById("toggle-mode").addEventListener("click", () => {
        mode = mode === "all" ? "sc" : "all";
        updateModeButton();
        updateStatsBar();
        renderTable();
        // Close any open detail panel since ranks change
        document.getElementById("player-detail").classList.add("hidden");
    });

    document.querySelectorAll("th.sortable").forEach(th => {
        th.addEventListener("click", () => {
            const key = th.dataset.sort;
            if (currentSort.key === key) {
                currentSort.dir = currentSort.dir === "asc" ? "desc" : "asc";
            } else {
                currentSort = { key, dir: key === "name" ? "asc" : "desc" };
            }
            document.querySelectorAll("th.sortable").forEach(h => h.classList.remove("active", "asc", "desc"));
            th.classList.add("active", currentSort.dir);
            renderTable();
        });
    });

    document.getElementById("close-detail").addEventListener("click", () => {
        document.getElementById("player-detail").classList.add("hidden");
    });
}

function updateModeButton() {
    const btn = document.getElementById("toggle-mode");
    if (mode === "sc") {
        btn.textContent = "Set Champs Only";
        btn.classList.add("mode-sc");
        btn.classList.remove("mode-all");
    } else {
        btn.textContent = "All Events";
        btn.classList.add("mode-all");
        btn.classList.remove("mode-sc");
    }
}

function showPlayerDetail(playerId) {
    const allPlayers = [...(leaderboardData.ranked || []), ...(leaderboardData.unranked || [])];
    const player = allPlayers.find(p => p.player_id === playerId);
    if (!player) return;

    const t = getTrack(player);
    const panel = document.getElementById("player-detail");
    panel.classList.remove("hidden");

    document.getElementById("detail-name").textContent = player.name;

    document.getElementById("detail-stats").innerHTML = `
        <div class="stat-card"><div class="value">${t.elo.toFixed(0)}</div><div class="label">ELO</div></div>
        <div class="stat-card"><div class="value">${t.record}</div><div class="label">Record</div></div>
        <div class="stat-card"><div class="value">${t.win_rate.toFixed(1)}%</div><div class="label">Win Rate</div></div>
        <div class="stat-card"><div class="value">${t.total_events}</div><div class="label">Events</div></div>
        <div class="stat-card"><div class="value">${t.total_matches}</div><div class="label">Matches</div></div>
        <div class="stat-card"><div class="value">${t.best_win_streak}</div><div class="label">Best Streak</div></div>
    `;

    drawEloChart(t.elo_history || []);
    renderEventRecords(player.event_records || []);

    panel.scrollIntoView({ behavior: "smooth" });
}

function renderEventRecords(events) {
    const container = document.getElementById("detail-events");
    if (!events.length) {
        container.innerHTML = "";
        return;
    }

    // Filter based on current mode
    const filtered = mode === "sc" ? events.filter(e => e.is_set_champ) : events;
    const modeLabel = mode === "sc" ? "Set Champ " : "";

    if (!filtered.length) {
        container.innerHTML = `<p class="muted">No ${modeLabel}tournaments found.</p>`;
        return;
    }

    const rows = filtered.map(e => {
        const scBadge = e.is_set_champ ? ' <span class="sc-badge">SC</span>' : "";
        const record = e.draws > 0 ? `${e.wins}-${e.losses}-${e.draws}` : `${e.wins}-${e.losses}`;
        const total = e.wins + e.losses + e.draws;
        const winPct = total > 0 ? ((e.wins / total) * 100).toFixed(0) + "%" : "—";
        const dateStr = e.date
            ? new Date(e.date + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
            : "—";
        return `<tr>
            <td>${escapeHtml(e.name)}${scBadge}</td>
            <td>${escapeHtml(e.store)}</td>
            <td>${dateStr}</td>
            <td>${record}</td>
            <td>${winPct}</td>
        </tr>`;
    }).join("");

    container.innerHTML = `
        <h3>${modeLabel}Tournaments (${filtered.length})</h3>
        <figure>
            <table>
                <thead><tr>
                    <th>Tournament</th><th>Store</th><th>Date</th><th>Record</th><th>Win%</th>
                </tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </figure>
    `;
}

function drawEloChart(history) {
    const canvas = document.getElementById("elo-chart");
    const ctx = canvas.getContext("2d");

    canvas.width = canvas.offsetWidth * 2;
    canvas.height = 400;
    ctx.scale(2, 2);
    const w = canvas.offsetWidth;
    const h = 200;

    ctx.clearRect(0, 0, w, h);

    if (history.length < 2) {
        ctx.fillStyle = "#888";
        ctx.font = "14px sans-serif";
        ctx.fillText("Not enough data for chart", w / 2 - 80, h / 2);
        return;
    }

    const elos = history.map(h => h[0]);
    const minElo = Math.floor(Math.min(...elos) / 50) * 50 - 50;
    const maxElo = Math.ceil(Math.max(...elos) / 50) * 50 + 50;
    const range = maxElo - minElo || 1;

    const pad = { top: 20, right: 20, bottom: 30, left: 50 };
    const chartW = w - pad.left - pad.right;
    const chartH = h - pad.top - pad.bottom;

    ctx.strokeStyle = "#333";
    ctx.lineWidth = 0.5;
    for (let e = minElo; e <= maxElo; e += 50) {
        const y = pad.top + chartH - ((e - minElo) / range) * chartH;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(w - pad.right, y);
        ctx.stroke();
        ctx.fillStyle = "#888";
        ctx.font = "11px sans-serif";
        ctx.textAlign = "right";
        ctx.fillText(e.toString(), pad.left - 5, y + 4);
    }

    ctx.strokeStyle = "#c9a84c";
    ctx.lineWidth = 2;
    ctx.beginPath();
    history.forEach((point, i) => {
        const x = pad.left + (i / (history.length - 1)) * chartW;
        const y = pad.top + chartH - ((point[0] - minElo) / range) * chartH;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();

    const drawDot = (i, color) => {
        const x = pad.left + (i / (history.length - 1)) * chartW;
        const y = pad.top + chartH - ((history[i][0] - minElo) / range) * chartH;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fill();
    };
    drawDot(0, "#888");
    drawDot(history.length - 1, "#c9a84c");
}

loadData();
