"""Plotly chart for a user's prediction history.

Colors follow the dark-surface values of the reference data-viz palette:
one series (blue) with its 90% interval as a translucent band.
"""

import plotly.graph_objects as go

SURFACE = "#1a1a19"
SERIES = "#3987e5"
BAND = "rgba(57, 135, 229, 0.18)"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#c3c2b7"
GRID = "#383835"


def trend_chart(predictions) -> str | None:
    """Predicted score over time, oldest -> newest. Needs at least 2 points."""
    points = sorted(predictions, key=lambda p: p.created_at)
    if len(points) < 2:
        return None

    x = [p.created_at for p in points]
    hover = [
        f"{p.predicted_score:.1f} (range {p.lower:.0f}–{p.upper:.0f}) · grade {p.grade}"
        for p in points
    ]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x + x[::-1],
        y=[p.upper for p in points] + [p.lower for p in points][::-1],
        mode="lines", fill="toself", fillcolor=BAND, line={"width": 0},
        hoverinfo="skip", showlegend=False, name="90% range",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=[p.predicted_score for p in points],
        mode="lines+markers", name="Predicted score",
        line={"color": SERIES, "width": 2},
        marker={"size": 8, "color": SERIES, "line": {"width": 2, "color": SURFACE}},
        customdata=hover, hovertemplate="%{customdata}<extra></extra>",
    ))
    fig.update_layout(
        height=320, margin={"l": 8, "r": 8, "t": 8, "b": 8},
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font={"color": TEXT_SECONDARY, "size": 13},
        hovermode="x unified",
        hoverlabel={"bgcolor": "#262624", "font": {"color": TEXT_PRIMARY}},
        showlegend=False,
        xaxis={"showgrid": False, "linecolor": GRID},
        yaxis={"range": [0, 100], "gridcolor": GRID, "zeroline": False,
               "title": {"text": "Score / 100"}},
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn",
                       config={"displayModeBar": False, "responsive": True})
