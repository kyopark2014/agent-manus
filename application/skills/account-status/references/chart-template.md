# HTML Chart Template Reference

This reference provides the structure and patterns for generating SFDC account revenue visualization charts.

## HTML Structure

### Required Dependencies
```html
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
```

### Email image / chart data (12-month trend block)

`html_to_chart_image.mjs`는 같은 구간의 `<script>` **const 배열**로 Chart.js를 다시 그립니다. **월별 매출 추이는 최근 12개월만** 표시합니다. **이메일용은 `…_chart.jpg` (가로 1000px·JPEG) 권장** — PNG/고해상도는 용량이 커 data URL/발송 제한에 걸리기 쉽습니다. **반드시** `id="lg-account-monthly-trend-12m"` 래퍼(소제목 + 차트)를 쓰고, `const months12`·시계열 배열이 **12개**가 되도록 맞춥니다.

```html
<section id="lg-account-monthly-trend-12m" style="padding: 16px; margin: 16px 0;">
    <h3>월별 매출 추이 (12개월)</h3>
    <div style="position: relative; height: 380px;">
        <canvas id="lgRevenueChart12m"></canvas>
    </div>
</section>
```

### CSS Styling Patterns

#### Summary Cards Grid
```css
.stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}
.stat-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 20px;
    border-radius: 8px;
}
```

#### Growth Analysis Box

**For Positive Growth:**
```css
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
```

**For Negative Growth:**
```css
background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
```

#### Growth Indicators
```css
.growth-indicator {
    display: inline-block;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: bold;
}
.growth-positive {
    background: #d4edda;
    color: #155724;
}
.growth-negative {
    background: #f8d7da;
    color: #721c24;
}
```

## Chart.js Configuration

### Data Structure
```javascript
const data = {
    labels: ['2025-04', '2025-05', ...], // 12 monthly labels
    datasets: [
        {
            label: 'Revenue (매출)',
            data: [226370, 458778, ...],
            borderColor: 'rgb(75, 192, 192)',
            backgroundColor: 'rgba(75, 192, 192, 0.1)',
            tension: 0.4,
            fill: true
        },
        {
            label: 'Charge (청구액)',
            data: [630353, 602501, ...],
            borderColor: 'rgb(153, 102, 255)',
            backgroundColor: 'rgba(153, 102, 255, 0.1)',
            tension: 0.4,
            fill: true
        }
    ]
};
```

### Chart Configuration
```javascript
const config = {
    type: 'line',
    data: data,
    options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            mode: 'index',
            intersect: false,
        },
        plugins: {
            tooltip: {
                callbacks: {
                    label: function(context) {
                        return context.dataset.label + ': $' + 
                               context.parsed.y.toLocaleString();
                    }
                }
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                ticks: {
                    callback: function(value) {
                        return '$' + (value / 1000).toFixed(0) + 'K';
                    }
                }
            }
        }
    }
};
```

## Growth Analysis Section Template

```html
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            padding: 20px; border-radius: 8px; margin-bottom: 20px; color: white;">
    <h3 style="margin: 0 0 15px 0; font-size: 18px; font-weight: bold;">
        📈 연간 성장률 분석
    </h3>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
        <div style="background: rgba(255,255,255,0.2); padding: 15px; border-radius: 6px;">
            <p style="margin: 0 0 8px 0; font-size: 13px; opacity: 0.9;">
                Rolling 12개월 비교
            </p>
            <p style="margin: 0; font-size: 24px; font-weight: bold;">
                +14.9% 📈
            </p>
            <p style="margin: 8px 0 0 0; font-size: 12px; opacity: 0.8;">
                $2.48M → $2.85M
            </p>
        </div>
        <div style="background: rgba(255,255,255,0.2); padding: 15px; border-radius: 6px;">
            <p style="margin: 0 0 8px 0; font-size: 13px; opacity: 0.9;">
                전년 동월 비교 (3월)
            </p>
            <p style="margin: 0; font-size: 24px; font-weight: bold;">
                +6.1% 📈
            </p>
            <p style="margin: 8px 0 0 0; font-size: 12px; opacity: 0.8;">
                $231.8K → $245.9K
            </p>
        </div>
    </div>
</div>
```

## Color Schemes by Company

Use different gradient schemes to distinguish multiple companies:

- **Company A**: `linear-gradient(135deg, #f093fb 0%, #f5576c 100%)` (Pink/Red)
- **Company B**: `linear-gradient(135deg, #667eea 0%, #764ba2 100%)` (Blue/Purple)
- **Company C**: `linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)` (Cyan)

## Data Formatting Functions

### Currency Formatting
```javascript
// In tooltips
'$' + value.toLocaleString()

// In axis ticks
'$' + (value / 1000).toFixed(0) + 'K'
```

### Growth Rate Formatting
```javascript
function formatGrowth(current, previous) {
    const growth = ((current - previous) / previous) * 100;
    const sign = growth >= 0 ? '+' : '';
    return sign + growth.toFixed(1) + '%';
}
```

### Emoji Indicators
- Positive growth: 📈
- Negative growth: 📉
- Neutral/stable: ➡️
