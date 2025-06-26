# app/services/plotresultsservice.py

from app.utils.plot import plot_and_save_chart

class PlotResultsService:
    @staticmethod
    def plot_equity_curve(equity_curve, symbol, out_dir):
        import matplotlib.pyplot as plt
        import os
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"equity_curve_{symbol}.png")
        plt.figure(figsize=(10, 6))
        plt.plot(equity_curve)
        plt.title(f'Equity Curve - {symbol}')
        plt.xlabel('Trade Number')
        plt.ylabel('Equity')
        plt.grid(True)
        plt.savefig(path)
        plt.close()
        return path
