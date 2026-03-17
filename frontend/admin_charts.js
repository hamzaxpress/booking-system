/**
 * admin_charts.js — Business Analytics for Admin Dashboard
 * ──────────────────────────────────────────────────────────
 * Renders three Chart.js charts using shipment data already
 * loaded by the portal. Called after renderDashboard() when
 * the logged-in user has role === 'admin'.
 *
 * Charts:
 *  1. Shipments by Status   — Doughnut / Pie chart
 *  2. Shipments Per Day     — Line chart (last 14 days)
 *  3. City Distribution     — Horizontal bar chart (origin city)
 *
 * No new API calls are made; data comes from state.shipments
 * which is already populated by loadDashboard().
 */

// ── Chart instance registry (so we can destroy before re-draw) ──────────────
window._adminCharts = window._adminCharts || {};

// ── Color palette matching the portal's CSS variables ───────────────────────
const AC_COLORS = {
  blue:    '#1565C0',
  blueMid: '#1976D2',
  bright:  '#2196F3',
  sky:     '#BBDEFB',
  teal:    '#00838F',
  green:   '#2E7D32',
  orange:  '#F57C00',
  purple:  '#6A1B9A',
  cyan:    '#0097A7',
  red:     '#C62828',
  amber:   '#FFB300',
  slate:   '#5C7FA3',
};

const STATUS_PALETTE = {
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

// ── Chart.js global defaults ─────────────────────────────────────────────────
function _setChartDefaults() {
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

// ── Helper: destroy existing chart instance safely ──────────────────────────
function _destroyChart(key) {
  if (window._adminCharts[key]) {
    try { window._adminCharts[key].destroy(); } catch(_) {}
    delete window._adminCharts[key];
  }
}

// ── 1. Shipments by Status — Doughnut ───────────────────────────────────────
function renderAdminStatusPieChart(shipments) {
  const canvas = document.getElementById('adminStatusPie');
  if (!canvas || !window.Chart) return;
  _destroyChart('statusPie');

  // Count by status code
  const counts = {};
  shipments.forEach(s => {
    const code = s.status?.code || 'UNKNOWN';
    counts[code] = (counts[code] || 0) + 1;
  });

  // Only include statuses with at least one shipment
  const entries = Object.entries(counts).filter(([,v]) => v > 0);
  if (entries.length === 0) {
    canvas.parentElement.querySelector('.chart-empty')?.remove();
    canvas.insertAdjacentHTML('afterend', '<p class="chart-empty" style="text-align:center;color:#5C7FA3;padding:24px 0;font-size:13px">No shipment data yet</p>');
    return;
  }

  const labels = entries.map(([code]) => {
    // Convert SNAKE_CASE to Title Case
    return code.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  });
  const data   = entries.map(([,v]) => v);
  const colors = entries.map(([code]) => STATUS_PALETTE[code] || AC_COLORS.slate);

  _setChartDefaults();
  window._adminCharts.statusPie = new Chart(canvas, {
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
      cutout: '62%',
      plugins: {
        legend: {
          position: 'right',
          labels: { boxWidth: 12, font: { size: 11 } },
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

// ── 2. Shipments Per Day — Line chart (last 14 days) ────────────────────────
function renderAdminDailyLineChart(shipments) {
  const canvas = document.getElementById('adminDailyLine');
  if (!canvas || !window.Chart) return;
  _destroyChart('dailyLine');

  // Build last-14-days date labels
  const today  = new Date();
  const labels = [];
  const dateKeys = [];
  for (let i = 13; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const key = d.toISOString().slice(0, 10); // YYYY-MM-DD
    dateKeys.push(key);
    labels.push(d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }));
  }

  // Count shipments per day using created_at or booking_date
  const dayCounts = {};
  dateKeys.forEach(k => dayCounts[k] = 0);
  shipments.forEach(s => {
    const raw = s.created_at || s.booking_date || '';
    if (!raw) return;
    const dayKey = raw.slice(0, 10);
    if (dayKey in dayCounts) dayCounts[dayKey]++;
  });

  const data = dateKeys.map(k => dayCounts[k]);

  _setChartDefaults();
  window._adminCharts.dailyLine = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Shipments Booked',
        data,
        borderColor:     AC_COLORS.blue,
        backgroundColor: 'rgba(21,101,192,0.10)',
        borderWidth: 2.5,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointBackgroundColor: AC_COLORS.blueMid,
        pointBorderColor: '#FFFFFF',
        pointBorderWidth: 2,
        fill: true,
        tension: 0.4,
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
            label: ctx => `  Shipments: ${ctx.parsed.y}`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: '#D0E4F7', lineWidth: 1 },
          ticks: { maxTicksLimit: 7, font: { size: 11 } },
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

// ── 3. City Distribution — Horizontal Bar chart ──────────────────────────────
function renderAdminCityBarChart(shipments) {
  const canvas = document.getElementById('adminCityBar');
  if (!canvas || !window.Chart) return;
  _destroyChart('cityBar');

  // Count by origin (sender) city
  const cityCounts = {};
  shipments.forEach(s => {
    const city = s.sender?.city?.trim() || 'Unknown';
    cityCounts[city] = (cityCounts[city] || 0) + 1;
  });

  // Sort descending, cap at top 10
  const sorted = Object.entries(cityCounts)
    .sort(([,a],[,b]) => b - a)
    .slice(0, 10);

  if (sorted.length === 0) return;

  const labels = sorted.map(([city]) => city);
  const data   = sorted.map(([,v]) => v);

  // Gradient color array from dark-blue to light-blue
  const barColors = data.map((_, i) => {
    const t = i / Math.max(data.length - 1, 1);
    const r = Math.round(21  + t * (33  - 21));
    const g = Math.round(101 + t * (150 - 101));
    const b = Math.round(192 + t * (243 - 192));
    return `rgba(${r},${g},${b},0.85)`;
  });

  _setChartDefaults();
  window._adminCharts.cityBar = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Shipments',
        data,
        backgroundColor: barColors,
        borderColor:     barColors.map(c => c.replace('0.85','1')),
        borderWidth: 1.5,
        borderRadius: 6,
        borderSkipped: false,
      }],
    },
    options: {
      indexAxis: 'y',   // horizontal
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => `  Shipments: ${ctx.parsed.x}`,
          },
        },
      },
      scales: {
        x: {
          beginAtZero: true,
          grid: { color: '#D0E4F7' },
          ticks: {
            stepSize: 1,
            callback: v => Number.isInteger(v) ? v : null,
          },
        },
        y: {
          grid: { display: false },
          ticks: { font: { size: 11 } },
        },
      },
    },
  });
}

// ── Master: render the HTML section + all three charts ───────────────────────
function renderAdminAnalyticsSection(shipments) {
  // Section is injected into #admin-analytics-mount by renderDashboard
  const mount = document.getElementById('admin-analytics-mount');
  if (!mount) return;

  mount.innerHTML = `
    <div style="margin-top:28px">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:18px">
        <div style="width:4px;height:22px;background:var(--blue);border-radius:4px"></div>
        <h2 style="font-family:'Syne',sans-serif;font-weight:700;font-size:17px;color:var(--navy)">
          Business Analytics
        </h2>
        <span style="font-size:12px;color:var(--muted);margin-left:4px">
          — based on ${shipments.length} shipment${shipments.length !== 1 ? 's' : ''}
        </span>
      </div>

      <!-- Row 1: Pie + Line -->
      <div style="display:grid;grid-template-columns:1fr 1.6fr;gap:20px;margin-bottom:20px">

        <!-- Status Pie -->
        <div class="card anim-up d3" style="padding:20px">
          <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:14px;margin-bottom:4px;color:var(--navy)">
            Shipments by Status
          </div>
          <div style="font-size:12px;color:var(--muted);margin-bottom:16px">Current status distribution</div>
          <div style="position:relative;height:220px">
            <canvas id="adminStatusPie"></canvas>
          </div>
        </div>

        <!-- Daily Line -->
        <div class="card anim-up d4" style="padding:20px">
          <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:14px;margin-bottom:4px;color:var(--navy)">
            Shipments Per Day
          </div>
          <div style="font-size:12px;color:var(--muted);margin-bottom:16px">Last 14 days booking activity</div>
          <div style="position:relative;height:220px">
            <canvas id="adminDailyLine"></canvas>
          </div>
        </div>
      </div>

      <!-- Row 2: City Bar (full width) -->
      <div class="card anim-up d5" style="padding:20px;margin-bottom:20px">
        <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:14px;margin-bottom:4px;color:var(--navy)">
          City Distribution
        </div>
        <div style="font-size:12px;color:var(--muted);margin-bottom:16px">Top origin cities by shipment count</div>
        <div style="position:relative;height:${Math.max(180, Math.min(Object.keys(
          shipments.reduce((acc,s)=>{ const c=s.sender?.city||'Unknown'; acc[c]=1; return acc; }, {})
        ).length, 10) * 36 + 40)}px">
          <canvas id="adminCityBar"></canvas>
        </div>
      </div>
    </div>
  `;

  // Render charts after DOM is painted
  requestAnimationFrame(() => {
    renderAdminStatusPieChart(shipments);
    renderAdminDailyLineChart(shipments);
    renderAdminCityBarChart(shipments);
  });
}
