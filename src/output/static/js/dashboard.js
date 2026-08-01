/* src/output/static/js/dashboard.js */

document.addEventListener('DOMContentLoaded', function () {
    loadStats();
    loadFilters();
    loadSourceChart();
    loadAppChart();
    loadRatingChart();
    loadDateRange();
    loadInsights();
    loadThemes();
    loadSegments();
    loadReviews();
    loadEval();
    loadUMAP();
    loadFaithfulnessChart();

    document.getElementById('global-search-form').addEventListener('submit', function (e) {
        e.preventDefault();
        const query = document.getElementById('global-search-input').value;
        document.getElementById('filter-search').value = query;
        document.getElementById('reviews').scrollIntoView({ behavior: 'smooth' });
        applyFilters();
    });
});

let currentReviewPage = 1;
let currentFilters = { search: '', source: '', app: '', rating: '' };

async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();

        document.getElementById('stat-raw-records').textContent = data.raw_records.toLocaleString();
        document.getElementById('stat-clean-chunks').textContent = data.clean_chunks.toLocaleString();
        document.getElementById('stat-sources').textContent = data.sources.length;
        document.getElementById('stat-apps').textContent = data.apps.length;
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

async function loadFilters() {
    try {
        const response = await fetch('/api/review-filters');
        const data = await response.json();

        const sourceSelect = document.getElementById('filter-source');
        data.sources.forEach(function (s) {
            const opt = document.createElement('option');
            opt.value = s;
            opt.textContent = s;
            sourceSelect.appendChild(opt);
        });

        const appSelect = document.getElementById('filter-app');
        data.apps.forEach(function (a) {
            const opt = document.createElement('option');
            opt.value = a;
            opt.textContent = a;
            appSelect.appendChild(opt);
        });
    } catch (error) {
        console.error('Failed to load filters:', error);
    }
}

async function loadSourceChart() {
    try {
        const response = await fetch('/api/review-distribution');
        const data = await response.json();

        const ctx = document.getElementById('sourceChart').getContext('2d');
        const sourceData = data.by_source;
        const labels = Object.keys(sourceData);
        const values = Object.values(sourceData);
        const colors = ['#0d6efd', '#198754', '#ffc107', '#dc3545', '#6c757d'];

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors.slice(0, labels.length),
                    borderWidth: 2,
                    borderColor: '#fff',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true,
                        },
                    },
                },
            },
        });
    } catch (error) {
        console.error('Failed to load source chart:', error);
    }
}

async function loadAppChart() {
    try {
        const response = await fetch('/api/review-distribution');
        const data = await response.json();

        const ctx = document.getElementById('appChart').getContext('2d');
        const appData = data.by_app;
        const labels = Object.keys(appData);
        const values = Object.values(appData);
        const colors = ['#0d6efd', '#198754', '#ffc107', '#dc3545', '#6f42c1'];

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Records',
                    data: values,
                    backgroundColor: colors.slice(0, labels.length),
                    borderWidth: 0,
                    borderRadius: 4,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false,
                    },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function (value) {
                                return value.toLocaleString();
                            },
                        },
                    },
                },
            },
        });
    } catch (error) {
        console.error('Failed to load app chart:', error);
    }
}

async function loadRatingChart() {
    try {
        const response = await fetch('/api/review-distribution');
        const data = await response.json();

        const ctx = document.getElementById('ratingChart').getContext('2d');
        const ratingData = data.by_rating;
        const labels = ['1 Star', '2 Stars', '3 Stars', '4 Stars', '5 Stars'];
        const values = [
            ratingData['1'] || 0,
            ratingData['2'] || 0,
            ratingData['3'] || 0,
            ratingData['4'] || 0,
            ratingData['5'] || 0,
        ];
        const colors = ['#dc3545', '#ffc107', '#fd7e14', '#198754', '#0d6efd'];

        new Chart(ctx, {
            type: 'polarArea',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors.map(function (c) {
                        return c + '99';
                    }),
                    borderWidth: 2,
                    borderColor: colors,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            usePointStyle: true,
                        },
                    },
                },
                scales: {
                    r: {
                        beginAtZero: true,
                        ticks: {
                            display: false,
                        },
                    },
                },
            },
        });
    } catch (error) {
        console.error('Failed to load rating chart:', error);
    }
}

async function loadDateRange() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();

        const dateRange = data.date_range;
        if (dateRange.earliest && dateRange.latest) {
            document.getElementById('date-range-text').textContent =
                dateRange.earliest + ' to ' + dateRange.latest;
        } else {
            document.getElementById('date-range-text').textContent = 'No date data available';
        }
    } catch (error) {
        console.error('Failed to load date range:', error);
    }
}

async function loadInsights() {
    const container = document.getElementById('insights-container');
    try {
        const response = await fetch('/api/insights');
        const data = await response.json();

        if (!data.insights || data.insights.length === 0) {
            container.innerHTML = '<div class="col-12"><div class="alert alert-info">No insights available yet. Run Phase 5 to generate insights.</div></div>';
            return;
        }

        let html = '';
        data.insights.forEach(function (insight) {
            const confidenceScore = insight.confidence || 0;
            const faithfulnessScore = insight.faithfulness_score;
            const faithfulnessPassed = insight.faithfulness_passed;

            const confidenceClass = confidenceScore >= 0.7 ? 'bg-success' : 'bg-warning';
            const confidenceLabel = confidenceScore >= 0.7 ? 'High' : 'Low';

            html += '<div class="col-md-6 col-lg-4">';
            html += '<div class="card insight-card mb-3 h-100">';
            html += '<div class="card-header bg-white d-flex justify-content-between align-items-center">';
            html += '<h6 class="mb-0 fw-bold">' + escapeHtml(insight.finding || 'Untitled Insight') + '</h6>';
            html += '<span class="badge ' + confidenceClass + ' badge-confidence">' + confidenceLabel + ' (' + confidenceScore.toFixed(2) + ')</span>';
            html += '</div>';
            html += '<div class="card-body d-flex flex-column">';
            html += '<p class="card-text implication-text flex-grow-1">' + escapeHtml(insight.implication || '') + '</p>';

            if (faithfulnessScore !== undefined && faithfulnessScore !== null) {
                const faithClass = faithfulnessPassed ? 'text-success' : 'text-danger';
                html += '<div class="mt-2 small ' + faithClass + '">';
                html += '<i class="bi bi-check-circle me-1"></i>Faithfulness: ' + faithfulnessScore.toFixed(2);
                html += ' <span class="badge bg-light text-dark">' + escapeHtml(insight.faithfulness_judge || '') + '</span>';
                html += '</div>';
            }

            if (insight.evidence && insight.evidence.length > 0) {
                html += '<div class="mt-2">';
                html += '<small class="text-muted fw-bold">Evidence:</small>';
                insight.evidence.forEach(function (ev) {
                    const quote = typeof ev === 'string' ? ev : (ev.quote || '');
                    if (quote) {
                        html += '<div class="evidence-quote mb-1">"' + escapeHtml(quote) + '"</div>';
                    }
                });
                html += '</div>';
            }

            if (insight.segment) {
                html += '<span class="badge bg-info segment-badge mt-2">' + escapeHtml(insight.segment) + '</span>';
            }

            html += '</div>';
            html += '</div>';
            html += '</div>';
        });

        container.innerHTML = html;
    } catch (error) {
        console.error('Failed to load insights:', error);
        container.innerHTML = '<div class="col-12"><div class="alert alert-danger">Failed to load insights.</div></div>';
    }
}

async function loadThemes() {
    const container = document.getElementById('themes-container');
    try {
        const response = await fetch('/api/themes');
        const data = await response.json();

        if (!data.themes || data.themes.length === 0) {
            container.innerHTML = '<div class="col-12"><div class="alert alert-info">No themes available yet. Run Phase 4 to generate themes.</div></div>';
            return;
        }

        let html = '';
        data.themes.forEach(function (theme) {
            html += '<div class="col-md-4">';
            html += '<div class="card theme-card mb-3 h-100">';
            html += '<div class="card-body">';
            html += '<h6 class="theme-name">' + escapeHtml(theme.theme_name || theme.name || 'Untitled Theme') + '</h6>';
            html += '<p class="theme-description">' + escapeHtml(theme.description || '') + '</p>';

            const quotes = theme.quotes || [];
            const validQuotes = quotes.filter(function (q) { return q && q.trim().length > 0; });
            if (validQuotes.length > 0) {
                validQuotes.slice(0, 3).forEach(function (quote) {
                    html += '<div class="theme-quote">"' + escapeHtml(quote) + '"</div>';
                });
            }

            html += '</div>';
            html += '</div>';
            html += '</div>';
        });

        container.innerHTML = html;
    } catch (error) {
        console.error('Failed to load themes:', error);
        container.innerHTML = '<div class="col-12"><div class="alert alert-danger">Failed to load themes.</div></div>';
    }
}

async function loadSegments() {
    const container = document.getElementById('segments-container');
    try {
        const response = await fetch('/api/segments');
        const data = await response.json();

        if (!data.segments || data.segments.length === 0) {
            container.innerHTML = '<div class="col-12"><div class="alert alert-info">No segment profiles available. Run Phase 5 to generate insights with segments.</div></div>';
            return;
        }

        let html = '';
        data.segments.forEach(function (seg) {
            html += '<div class="col-md-6 col-lg-4">';
            html += '<div class="card segment-card mb-3 h-100">';
            html += '<div class="card-header bg-white">';
            html += '<h6 class="mb-0 fw-bold text-primary">' + escapeHtml(seg.segment) + '</h6>';
            html += '</div>';
            html += '<div class="card-body">';
            html += '<p class="mb-1"><strong>Insights:</strong> ' + seg.insight_count + '</p>';
            html += '<p class="mb-1"><strong>Avg Confidence:</strong> ' + seg.average_confidence.toFixed(2) + '</p>';
            html += '<p class="mb-1"><strong>Research Questions:</strong></p>';
            html += '<ul class="list-unstyled mb-2">';
            seg.research_questions.forEach(function (rq) {
                html += '<li><i class="bi bi-arrow-right-short text-primary me-1"></i>' + escapeHtml(rq) + '</li>';
            });
            html += '</ul>';
            html += '</div>';
            html += '</div>';
            html += '</div>';
        });

        container.innerHTML = html;
    } catch (error) {
        console.error('Failed to load segments:', error);
        container.innerHTML = '<div class="col-12"><div class="alert alert-danger">Failed to load segments.</div></div>';
    }
}

async function loadReviews() {
    currentReviewPage = 1;
    await fetchReviews();
}

async function fetchReviews() {
    const tbody = document.getElementById('reviews-tbody');
    const countEl = document.getElementById('review-count');
    try {
        const params = new URLSearchParams({
            page: currentReviewPage,
            page_size: 25,
            search: currentFilters.search,
            source: currentFilters.source,
            app: currentFilters.app,
            rating: currentFilters.rating,
        });

        const response = await fetch('/api/reviews?' + params.toString());
        const data = await response.json();

        if (!data.reviews || data.reviews.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No reviews found.</td></tr>';
            countEl.textContent = '0 reviews';
            document.getElementById('pagination-controls').innerHTML = '';
            return;
        }

        let html = '';
        data.reviews.forEach(function (review) {
            const ratingBadge = review.rating
                ? '<span class="badge bg-warning text-dark">' + review.rating + '★</span>'
                : '<span class="badge bg-secondary">N/A</span>';

            html += '<tr>';
            html += '<td><span class="badge bg-primary">' + escapeHtml(review.source || '') + '</span></td>';
            html += '<td>' + escapeHtml(review.app || '') + '</td>';
            html += '<td>' + ratingBadge + '</td>';
            html += '<td>' + escapeHtml(review.date || '') + '</td>';
            html += '<td class="text-truncate" style="max-width: 400px;" title="' + escapeHtml(review.text || '') + '">' + escapeHtml(review.text || '') + '</td>';
            html += '</tr>';
        });

        tbody.innerHTML = html;
        countEl.textContent = 'Showing ' + data.count + ' of ' + data.total + ' reviews';

        renderPagination(data.total, data.page_size, data.page);
    } catch (error) {
        console.error('Failed to load reviews:', error);
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Failed to load reviews.</td></tr>';
    }
}

function renderPagination(total, pageSize, currentPage) {
    const totalPages = Math.ceil(total / pageSize);
    const controls = document.getElementById('pagination-controls');
    if (totalPages <= 1) {
        controls.innerHTML = '';
        return;
    }

    let html = '';
    html += '<li class="page-item ' + (currentPage === 1 ? 'disabled' : '') + '">';
    html += '<a class="page-link" href="#" onclick="changePage(' + (currentPage - 1) + '); return false;">Previous</a>';
    html += '</li>';

    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 1 && i <= currentPage + 1)) {
            html += '<li class="page-item ' + (i === currentPage ? 'active' : '') + '">';
            html += '<a class="page-link" href="#" onclick="changePage(' + i + '); return false;">' + i + '</a>';
            html += '</li>';
        } else if (i === currentPage - 2 || i === currentPage + 2) {
            html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
        }
    }

    html += '<li class="page-item ' + (currentPage === totalPages ? 'disabled' : '') + '">';
    html += '<a class="page-link" href="#" onclick="changePage(' + (currentPage + 1) + '); return false;">Next</a>';
    html += '</li>';

    controls.innerHTML = html;
}

function changePage(page) {
    currentReviewPage = page;
    fetchReviews();
    document.getElementById('reviews').scrollIntoView({ behavior: 'smooth' });
}

function applyFilters() {
    currentFilters.search = document.getElementById('filter-search').value;
    currentFilters.source = document.getElementById('filter-source').value;
    currentFilters.app = document.getElementById('filter-app').value;
    currentFilters.rating = document.getElementById('filter-rating').value;
    currentReviewPage = 1;
    fetchReviews();
}

function resetFilters() {
    document.getElementById('filter-search').value = '';
    document.getElementById('filter-source').value = '';
    document.getElementById('filter-app').value = '';
    document.getElementById('filter-rating').value = '';
    currentFilters = { search: '', source: '', app: '', rating: '' };
    currentReviewPage = 1;
    fetchReviews();
}

async function loadEval() {
    try {
        const response = await fetch('/api/eval');
        const data = await response.json();

        document.getElementById('eval-passed').textContent = data.passed ? 'YES' : 'NO';
        document.getElementById('eval-passed').className = 'stat-number ' + (data.passed ? 'text-success' : 'text-danger');

        const faith = data.faithfulness || {};
        const avgScore = faith.average_score || 0;
        document.getElementById('eval-faithfulness').textContent = avgScore.toFixed(2);

        const coverage = data.coverage || {};
        const coverageCount = coverage.coverage_count || 0;
        const totalQuestions = coverage.total_questions || 8;
        document.getElementById('eval-coverage').textContent = coverageCount + '/' + totalQuestions;

        const contradictions = data.contradictions || {};
        const unresolved = contradictions.unresolved ? contradictions.unresolved.length : 0;
        document.getElementById('eval-contradictions').textContent = unresolved;

        const perInsight = faith.per_insight || {};
        const tbody = document.getElementById('faithfulness-tbody');
        const countBadge = document.getElementById('faithfulness-count');

        const entries = Object.entries(perInsight);
        countBadge.textContent = entries.length + ' insights';

        let html = '';
        entries.forEach(function ([qid, info]) {
            const score = info.faithfulness_score || 0;
            const passed = info.faithfulness_passed ? 'text-success' : 'text-danger';
            const passedLabel = info.faithfulness_passed ? 'PASS' : 'FAIL';

            html += '<tr>';
            html += '<td>' + escapeHtml(qid) + '</td>';
            html += '<td>' + escapeHtml(info.research_question_id || qid) + '</td>';
            html += '<td>' + score.toFixed(2) + '</td>';
            html += '<td class="' + passed + ' fw-bold">' + passedLabel + '</td>';
            html += '<td>' + escapeHtml(info.judge || '') + '</td>';
            html += '<td>' + escapeHtml(info.reasoning || '') + '</td>';
            html += '</tr>';
        });

        tbody.innerHTML = html || '<tr><td colspan="6" class="text-center text-muted">No faithfulness scores available.</td></tr>';
    } catch (error) {
        console.error('Failed to load eval:', error);
    }
}

async function loadUMAP() {
    try {
        const response = await fetch('/api/umap?format=image');
        const data = await response.json();

        const img = document.getElementById('umap-image');
        const loading = document.getElementById('umap-loading');
        const unavailable = document.getElementById('umap-unavailable');

        if (data.exists) {
            img.src = data.image_url;
            img.style.display = 'block';
            loading.style.display = 'none';
            unavailable.style.display = 'none';
        } else {
            img.style.display = 'none';
            loading.style.display = 'none';
            unavailable.style.display = 'block';
        }
    } catch (error) {
        console.error('Failed to load UMAP:', error);
        document.getElementById('umap-loading').style.display = 'none';
        document.getElementById('umap-unavailable').style.display = 'block';
    }
}

async function loadFaithfulnessChart() {
    try {
        const response = await fetch('/api/eval');
        const data = await response.json();
        const perInsight = data.faithfulness?.per_insight || {};

        const labels = [];
        const scores = [];
        const colors = [];

        Object.entries(perInsight).forEach(function ([qid, info]) {
            labels.push(qid);
            scores.push(info.faithfulness_score || 0);
            colors.push(info.faithfulness_passed ? '#198754' : '#dc3545');
        });

        if (labels.length === 0) return;

        const ctx = document.getElementById('faithfulnessChart').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Faithfulness Score',
                    data: scores,
                    backgroundColor: colors.map(function (c) { return c + '99'; }),
                    borderColor: colors,
                    borderWidth: 1,
                    borderRadius: 4,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 1.0,
                        ticks: {
                            callback: function (value) {
                                return value.toFixed(1);
                            },
                        },
                    },
                },
            },
        });
    } catch (error) {
        console.error('Failed to load faithfulness chart:', error);
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
