// ---- 주간 그래프 ----
// 기록이 없는 계정은 캔버스가 없고, 인터넷이 안 되면 Chart.js를 못 불러올 수 있다.
// 어느 쪽이어도 아래 AI 버튼 코드까지 멈추지 않도록 검사한 뒤에만 그린다.
const chartCanvas = document.getElementById('weekChart');
if (chartCanvas && typeof Chart !== 'undefined') {
  const data = JSON.parse(document.getElementById('chart-data').textContent);

  // 색은 style.css의 변수(--s1-bg ~ --s5-bg, --line)를 그대로 읽어 온다.
  // 그래서 목록, 달력, 범례, 그래프가 항상 같은 색을 쓴다.
  const css = getComputedStyle(document.documentElement);
  const cssVar = (name) => css.getPropertyValue(name).trim();
  const scoreColor = (score) => cssVar(`--s${score}-bg`);
  const SCORE_NAMES = { 1: '매우 나쁨', 2: '나쁨', 3: '보통', 4: '좋음', 5: '매우 좋음' };

  Chart.defaults.font.family = cssVar('--font');
  Chart.defaults.color = cssVar('--muted');

  new Chart(chartCanvas, {
    type: 'line',
    data: {
      labels: data.labels,
      datasets: [{
        label: '기분 점수',
        data: data.scores,      // null인 날은 점이 찍히지 않는다
        borderColor: cssVar('--line'),
        borderWidth: 2,
        tension: 0.25,
        spanGaps: true,         // 기록 없는 날은 건너뛰고 선을 이어 준다
        pointRadius: 8,
        pointHoverRadius: 10,
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
        // 점마다 그날 점수에 맞는 색 (낮으면 파랑, 높으면 주황)
        pointBackgroundColor: data.scores.map((s) => (s ? scoreColor(s) : 'transparent')),
      }],
    },
    options: {
      scales: {
        // 점이 가장자리에 걸리지 않게 위아래로 0.5씩 여유를 두고, 눈금은 점수인 1~5에만 찍는다
        y: {
          min: 0.5,
          max: 5.5,
          afterBuildTicks: (axis) => { axis.ticks = [1, 2, 3, 4, 5].map((value) => ({ value })); },
          grid: { color: cssVar('--border') },
          border: { display: false },
        },
        x: { grid: { display: false } },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: (ctx) => ` ${ctx.parsed.y}점 · ${SCORE_NAMES[ctx.parsed.y]}` },
        },
      },
    },
  });
} else if (chartCanvas) {
  chartCanvas.insertAdjacentHTML(
    'afterend',
    '<p class="hint">그래프를 불러오지 못했어요. 인터넷 연결을 확인해 주세요.</p>'
  );
}

// ---- AI 리포트 버튼 ----
// AI 답변의 마크다운 별표를 처리한다: **굵게** -> 굵은 글씨, 줄 앞의 "* " -> "• ".
// innerHTML을 쓰지 않고 <strong> 요소를 직접 만들어서, AI 응답이 HTML로 해석되지 않게 한다.
function renderReport(box, text) {
  box.textContent = '';
  const cleaned = text.replace(/^(\s*)[*-]\s+/gm, '$1• ');
  cleaned.split(/\*\*(.+?)\*\*/gs).forEach((part, i) => {
    if (i % 2 === 1) {
      const strong = document.createElement('strong');
      strong.textContent = part;
      box.appendChild(strong);
    } else {
      box.appendChild(document.createTextNode(part.replace(/\*\*/g, '')));   // 짝 없는 ** 는 지운다
    }
  });
}

const FRIENDLY_ERROR = '지금은 리포트를 만들 수 없어요. 잠시 후 다시 시도해 주세요.';
const reportBtn = document.getElementById('reportBtn');
const reportBox = document.getElementById('reportBox');

if (reportBtn && reportBox) {
  reportBtn.addEventListener('click', async () => {
    reportBtn.disabled = true;
    reportBtn.textContent = '분석 중...';
    reportBox.hidden = false;
    reportBox.classList.remove('error');
    reportBox.textContent = 'AI가 기록을 읽고 있어요. 잠시만 기다려 주세요.';

    // 서버가 응답하지 않아도 화면이 영원히 "분석 중"에 멈추지 않도록 45초 후 포기한다
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 45000);

    try {
      const res = await fetch(reportBtn.dataset.url, {
        method: 'POST',
        headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value },
        signal: controller.signal,
      });
      const body = await res.json();   // 서버 오류 화면(HTML)이 오면 여기서 예외 → 아래 catch
      if (res.ok && body.report) {
        renderReport(reportBox, body.report);   // 텍스트 노드와 <strong>만 만든다 (HTML로 해석하지 않음)
      } else {
        reportBox.classList.add('error');
        reportBox.textContent = body.error || FRIENDLY_ERROR;
      }
    } catch (e) {
      reportBox.classList.add('error');
      reportBox.textContent = FRIENDLY_ERROR;
    } finally {
      clearTimeout(timer);
      reportBtn.disabled = false;
      reportBtn.textContent = 'AI 리포트 다시 받기';
    }
  });
}
