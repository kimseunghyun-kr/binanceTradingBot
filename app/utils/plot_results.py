import os

import numpy as np
import plotly.graph_objects as go


def plot_grid_search_3d(results, plot_dir):
    param_names = list(results[0][0].keys())
    tp = [r[0].get("tp_ratio") for r in results]
    sl = [r[0].get("sl_ratio") for r in results]
    returns = [r[1] for r in results]
    x = np.array(tp)
    y = np.array(sl)
    z = np.array(returns)
    fig = go.Figure(data=[go.Scatter3d(
        x=x * 100, y=y * 100, z=z,
        mode='markers',
        marker=dict(size=6, color=z, colorscale='RdBu', colorbar=dict(title='Return (%)')),
        text=[f"TP={tpv * 100:.2f}%, SL={slv * 100:.2f}%, Return={ret:.2f}%" for tpv, slv, ret in zip(x, y, z)],
        hoverinfo='text'
    )])
    fig.update_layout(
        title="Grid Search Results",
        scene=dict(xaxis_title="Take Profit (%)", yaxis_title="Stop Loss (%)", zaxis_title="Return (%)")
    )
    os.makedirs(plot_dir, exist_ok=True)
    file_path = os.path.join(plot_dir, "grid_search_3d.html")
    fig.write_html(file_path)
    return file_path
