/**
 * staff_charts.js — Operations Overview for Staff Dashboard
 * ──────────────────────────────────────────────────────────
 * Renders three Chart.js charts using shipment data already
 * loaded by the portal. Called after renderDashboard() for
 * users with role === 'staff' (and also admins if desired).
 *
 * Charts:
 *  1. Today's Shipments    — Vertical bar chart (hourly)
 *  2. Status Breakdown     — Pie / Doughnut chart
 *  3. Weekly Activity      — Line chart (last 7 days)
 *
 * No new API calls are made; data comes from state.shipments.
 */

// ── Chart instance registry ──────────────────────────────────────────────────
window._staffCharts = window._staffCharts || {};

// ── Color palette ────────────────────────────────────────────────────────────
const SC_COLORS = {
  blue:   '#1565C0',
  mid:    '#1976D2',
  bright: '#2196F3',
  teal:   '#00838F',
  green:  '#2E7D32',
  orange: '#F57C00',
  slate:  '#5C7FA3',
  sky:    '#BBDEFB',
};

const SC_STATUS_PALETTE = {
  BOOKED:             '#1976D2',
  PICKUP_SCHEDULED:   '#8B5CF6',
  PICKED_UP:          '#F59E0B',
  AT_ORIGIN_HUB:      '#F97316',
  IN_TRANSIT:         '#06B6D4',
  AT_DESTINATION_HUB: '#6366F1',
  OUT_FOR_DELIVERY:   '#10B981',
  DELIVERED:          '#22C55E',
  DELIVERY_ATTEMPTED: '#EAB308',
  RETURNED_TO_HUB:    '#F87171',
  LOST:               '#EF4444',
  CANCELLED:          '#94A3B8',
  DAMAGED:            '#DC2626',
};

// ── Helper: destroy chart safely ─────────────────────────────────────────────
function _destroyStaffChart(key) {
  if (window._staffCharts[key]) {
    try { window._staffCharts[key].destroy(); } catch(_) {}
    delete window._staffCharts[key];
  }
}

// ── Chart.js global defaults (safe to call multiple times) ───────────────────
function _setStaffChartDefaults() {
  if (!window.Chart) return;
  Chart.defaults.font.family = "'DM Sans', sans-serif";
  Chart.defaults.font.size   = 12;
  Chart.defaults.color       = '#5C7FA3';
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.padding = 16;
  Chart.defaults.plugins.tooltip.backgroundColor = '#0B1F3A';
  Chart.defaults.plugins.tooltip.titleColor      = '#FFFFFF';
  Chart.defaults.plugins.tooltip.bodyColor       = '#BBDEFB';
  Chart.defaults.plugins.tooltip.padding         = 12;
  Chart.defaults.plugins.tooltip.cornerRadius    = 8;
}

// ── 1. Today's Shipments — Hourly Bar chart ──────────────────────────────────
function renderStaffTodayBarChart(shipments) {
  const canvas = document.getElementById('staffTodayBar');
  if (!canvas || !window.Chart) return;
  _destroyStaffChart('todayBar');

  const todayStr = new Date().toISOString().slice(0, 10);

  // Bucket into 4-hour slots: 00–04, 04–08, ..., 20–24
  const slots    = ['12am–4am','4am–8am','8am–12pm','12pm–4pm','4pm–8pm','8pm–12am'];
  const slotData = new Array(6).fill(0);

  shipments.forEach(s => {
    const raw = s.created_at || s.booking_date || '';
    if (!raw || !raw.startsWith(todayStr)) return;
    // Parse hour from ISO string (UTC stored, display as-is)
    const timeStr = raw.slice(11, 13);
    const hour    = parseInt(timeStr, 10) || 0;
    const slot    = Math.floor(hour / 4);
    if (slot >= 0 && slot < 6) slotData[slot]++;
  });

  const total = slotData.reduce((a,b) => a+b, 0);

  _setStaffChartDefaults();
  window._staffCharts.todayBar = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: slots,
      datasets: [{
        label: "Today's Shipments",
        data: slotData,
        backgroundColor: slotData.map(v =>
          v > 0 ? 'rgba(21,101,192,0.80)' : 'rgba(208,228,247,0.6)'
        ),
        borderColor: slotData.map(v =>
          v > 0 ? SC_COLORS.blue : SC_COLORS.sky
        ),
        borderWidth: 1.5,
        borderRadius: 6,
        borderSkipped: false,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: {
          display: total === 0,
          text: 'No shipments booked today yet',
          color: SC_COLORS.slate,
          font: { size: 12 },
        },
        tooltip: {
          callbacks: {
            label: ctx => `  Shipments: ${ctx.parsed.y}`,
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { size: 11 } },
        },
        y: {
          beginAtZero: true,
          grid: { color: '#D0E4F7' },
          ticks: {
            stepSize: 1,
            callback: v => Number.isInteger(v) ? v : null,
          },
        },
      },
    },
  });
}

// ── 2. Status Breakdown — Doughnut ───────────────────────────────────────────
function renderStaffStatusPieChart(shipments) {
  const canvas = document.getElementById('staffStatusPie');
  if (!canvas || !window.Chart) return;
  _destroyStaffChart('statusPie');

  const counts = {};
  shipments.forEach(s => {
    const code = s.status?.code || 'UNKNOWN';
    counts[code] = (counts[code] || 0) + 1;
  });

  const entries = Object.entries(counts).filter(([,v]) => v > 0);
  if (entries.length === 0) return;

  const labels = entries.map(([code]) =>
    code.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  );
  const data   = entries.map(([,v]) => v);
  const colors = entries.map(([code]) => SC_STATUS_PALETTE[code] || SC_COLORS.slate);

  _setStaffChartDefaults();
  window._staffCharts.statusPie = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: colors,
        borderColor: '#FFFFFF',
        borderWidth: 3,
        hoverOffset: 8,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '60%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { boxWidth: 12, font: { size: 10 }, padding: 10 },
        },
        tooltip: {
          callbacks: {
            label: ctx => {
              const total = ctx.dataset.data.reduce((a,b) => a+b, 0);
              const pct   = total ? Math.round(ctx.parsed / total * 100) : 0;
              return `  ${ctx.label}: ${ctx.parsed} (${pct}%)`;
            },
          },
        },
      },
    },
  });
}

// ── 3. Weekly Activity — Line chart ─────────────────────────────────────────
function renderStaffWeeklyLineChart(shipments) {
  const canvas = document.getElementById('staffWeeklyLine');
  if (!canvas || !window.Chart) return;
  _destroyStaffChart('weeklyLine');

  const today   = new Date();
  const labels  = [];
  const dateKeys = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    dateKeys.push(d.toISOString().slice(0, 10));
    labels.push(d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric' }));
  }

  const dayCounts = {};
  dateKeys.forEach(k => dayCounts[k] = 0);
  shipments.forEach(s => {
    const raw = s.created_at || s.booking_date || '';
    const key = raw.slice(0, 10);
    if (key in dayCounts) dayCounts[key]++;
  });

  const data = dateKeys.map(k => dayCounts[k]);

  // Two datasets: bookings + (simulated) delivered count from 'DELIVERED' status
  const deliveredCounts = {};
  dateKeys.forEach(k => deliveredCounts[k] = 0);
  // We don't have per-day delivered info without event timestamps, so skip
  // and just show total booked per day

  _setStaffChartDefaults();
  window._staffCharts.weeklyLine = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Booked',
        data,
        borderColor:     SC_COLORS.blue,
        backgroundColor: 'rgba(21,101,192,0.10)',
        borderWidth: 2.5,
        pointRadius: 5,
        pointHoverRadius: 7,
        pointBackgroundColor: SC_COLORS.mid,
        pointBorderColor: '#FFFFFF',
        pointBorderWidth: 2,
        fill: true,
        tension: 0.35,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: ctx => ctx[0].label,
            label: ctx => `  Bookings: ${ctx.parsed.y}`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: '#D0E4F7' },
          ticks: { font: { size: 11 } },
        },
        y: {
          beginAtZero: true,
          grid: { color: '#D0E4F7' },
          ticks: {
            stepSize: 1,
            callback: v => Number.isInteger(v) ? v : null,
          },
        },
      },
    },
  });
}

// ── Master: inject HTML section + render all charts ─────────────────────────
function renderStaffOperationsSection(shipments) {
  const mount = document.getElementById('staff-analytics-mount');
  if (!mount) return;

  mount.innerHTML = `
    <div style="margin-top:28px">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:18px">
        <div style="width:4px;height:22px;background:var(--teal,#00838F);border-radius:4px"></div>
        <h2 style="font-family:'Syne',sans-serif;font-weight:700;font-size:17px;color:var(--navy)">
          Operations Overview
        </h2>
        <span style="font-size:12px;color:var(--muted);margin-left:4px">
          — ${shipments.length} shipment${shipments.length !== 1 ? 's' : ''} tracked
        </span>
      </div>

      <!-- Row 1: Today bar + Status pie -->
      <div style="display:grid;grid-template-columns:1.6fr 1fr;gap:20px;margin-bottom:20px">

        <!-- Today's Shipments -->
        <div class="card anim-up d3" style="padding:20px">
          <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:14px;margin-bottom:4px;color:var(--navy)">
            Today's Shipments
          </div>
          <div style="font-size:12px;color:var(--muted);margin-bottom:16px">Bookings by time of day</div>
          <div style="position:relative;height:200px">
            <canvas id="staffTodayBar"></canvas>
          </div>
        </div>

        <!-- Status Breakdown Pie -->
        <div class="card anim-up d4" style="padding:20px">
          <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:14px;margin-bottom:4px;color:var(--navy)">
            Status Breakdown
          </div>
          <div style="font-size:12px;color:var(--muted);margin-bottom:16px">All shipments</div>
          <div style="position:relative;height:200px">
            <canvas id="staffStatusPie"></canvas>
          </div>
        </div>
      </div>

      <!-- Row 2: Weekly Line (full width) -->
      <div class="card anim-up d5" style="padding:20px;margin-bottom:20px">
        <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:14px;margin-bottom:4px;color:var(--navy)">
          Weekly Activity
        </div>
        <div style="font-size:12px;color:var(--muted);margin-bottom:16px">Shipments booked over the last 7 days</div>
        <div style="position:relative;height:200px">
          <canvas id="staffWeeklyLine"></canvas>
        </div>
      </div>
    </div>
  `;

  requestAnimationFrame(() => {
    renderStaffTodayBarChart(shipments);
    renderStaffStatusPieChart(shipments);
    renderStaffWeeklyLineChart(shipments);
  });
}
