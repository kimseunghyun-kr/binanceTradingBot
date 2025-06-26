#!/usr/bin/env python3
import time
import logging
import schedule
import os
import sys
from analyzeData import run_weekly_analysis, run_daily_analysis
from config import ANALYSIS_SYMBOLS
from symbols import initialize_symbols
from backtest import run_backtesting, plot_grid_search_results, clear_signals_cache

# Try to import analysis functions from backtest_analysis.py
try:
    sys.path.append('backtest_results')
    from backtest_results.backtest_analysis import analyze_single_add_buy_folder
    ANALYSIS_AVAILABLE = True
    logging.info("Portfolio analysis module loaded successfully.")
except ImportError as e:
    logging.warning(f"Portfolio analysis module not available: {e}")
    logging.warning("Continuing without portfolio analysis feature.")
    ANALYSIS_AVAILABLE = False
    
    # Create a dummy function
    def analyze_single_add_buy_folder(target_directory, create_charts=True):
        logging.warning("Portfolio analysis skipped - required modules not installed.")
        return False

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.info("Starting Kwon's Strategy Bot with local-variable fix, sir...")

    initialize_symbols()
    if not ANALYSIS_SYMBOLS:
        logging.info("No symbols available for analysis. Exiting, sir.")
        return
    
    print("Do you want to run a backtesting? (y: backtest/n: current-test), sir.")
    backtest_choice = input(">").strip().lower()
    if backtest_choice.startswith("y"):
        print("Which timeframe do you want to test? (1w: weekly/1d: daily), sir.")
        tf = input(">").strip().lower()
        print("Do you want to save charts? (y: save/n: no save), sir.")
        save_charts = input(">").strip().lower()
        save_charts = True if save_charts.startswith("y") else False

        # Ask if user wants to run analysis after backtesting
        if ANALYSIS_AVAILABLE:
            print("Do you want to run portfolio analysis after backtesting? (y/n), sir.")
            run_analysis = input(">").strip().lower().startswith("y")
            
            if run_analysis:
                print("Do you want to generate position charts during analysis? (y/n), sir.")
                create_position_charts = input(">").strip().lower().startswith("y")
            else:
                create_position_charts = False
        else:
            print("Portfolio analysis module not available. Only backtesting will be performed.")
            run_analysis = False
            create_position_charts = False

        # Get add_buy_pcts
        add_buy_pcts = []
        print("Do you want to do a grid search for additional buy percentage? (y/n), sir.")
        add_buy_grid_choice = input(">").strip().lower()
        if add_buy_grid_choice.startswith("y"):
            print("Enter initial add_buy_pct (e.g., 2.0 for 2.0% drop):")
            add_buy_start = float(input(">"))
            print("Enter final add_buy_pct (e.g., 10.0 for 10.0% drop):")
            add_buy_final = float(input(">"))
            print("Enter step for add_buy_pct (e.g., 1.0 for 1.0% step):")
            add_buy_step = float(input(">"))
            # Ensure positive step and correct range
            if add_buy_step <= 0:
                print("Warning: Add_buy_pct step must be positive. Defaulting to single value of start_add_buy_pct.")
                add_buy_pcts = [round(add_buy_start, 1)]
            elif add_buy_final < add_buy_start:
                print("Warning: Final add_buy_pct is less than initial. Using only initial add_buy_pct.")
                add_buy_pcts = [round(add_buy_start, 1)]
            else:
                num_steps = int((add_buy_final - add_buy_start) / add_buy_step) + 1
                add_buy_pcts = [round(add_buy_start + i * add_buy_step, 1) for i in range(num_steps)]
        else:
            print("Enter price drop % for additional buy (e.g., 5.0 for -5.0% from initial price):")
            single_add_buy_pct = float(input(">"))
            add_buy_pcts = [round(single_add_buy_pct, 1)]

        # Get TP/SL ratios
        tp_ratios_list = []
        sl_ratios_list = []
        print("Do you want to do grid search for TP/SL? (y: grid search/n: single test), sir.")
        tp_sl_grid_choice = input(">").strip().lower()
        if tp_sl_grid_choice.startswith("y"):
            print("Enter the initial TP ratio (e.g., 0.1 for 10%):")
            tp_ratio_start = float(input(">"))
            print("Enter the final TP ratio (e.g., 0.2 for 20%):")
            tp_ratio_final = float(input(">"))
            print("Enter the step size for TP ratio (e.g., 0.01 for 1%):")
            tp_step = float(input(">"))
            print("Enter the initial SL ratio (e.g., 0.05 for 5%):")
            sl_ratio_start = float(input(">"))
            print("Enter the final SL ratio (e.g., 0.2 for 20%):")
            sl_ratio_final = float(input(">"))
            print("Enter the step size for SL ratio (e.g., 0.01 for 1%):")
            sl_step = float(input(">"))
            
            if tp_step <=0 or sl_step <= 0:
                print("Warning: TP/SL step must be positive. Exiting.")
                return
            if tp_ratio_final < tp_ratio_start or sl_ratio_final < sl_ratio_start:
                print("Warning: Final TP/SL is less than initial. Exiting.")
                return

            tp_ratios_list = [round(tp_ratio_start + i * tp_step, 3) 
                         for i in range(int((tp_ratio_final - tp_ratio_start) / tp_step) + 1)]
            sl_ratios_list = [round(sl_ratio_start + i * sl_step, 3) 
                         for i in range(int((sl_ratio_final - sl_ratio_start) / sl_step) + 1)]
        else:
            print("Enter the TP ratio (e.g., 0.1 for 10%):")
            tp_ratio = float(input(">"))
            print("Enter the SL ratio (e.g., 0.05 for 5%):")
            sl_ratio = float(input(">"))
            tp_ratios_list = [tp_ratio]
            sl_ratios_list = [sl_ratio]

        # Main loops
        for current_add_buy_pct_val in add_buy_pcts:
            logging.info(f"\n--- Testing with Additional Buy Percentage: {current_add_buy_pct_val:.1f}% ---")
            grid_results_for_tp_sl = [] 

            # Track if this is the first run for cache initialization
            first_run = True

            for tp_r_val in tp_ratios_list:
                for sl_r_val in sl_ratios_list:
                    logging.info(f"\nRunning backtest: TF={tf}, TP={round(tp_r_val*100, 2)}%, SL={round(sl_r_val*100, 2)}%, Add.Buy={current_add_buy_pct_val:.1f}%")
                    
                    # Use cache for all runs except the first one
                    use_cache = not first_run
                    if first_run:
                        logging.info("First grid search run - collecting signals and building cache...")
                        first_run = False
                    else:
                        logging.info("Using cached signals for faster processing...")
                    
                    results = run_backtesting(tf, tp_r_val, sl_r_val, save_charts, current_add_buy_pct_val, use_cache=use_cache) 
                    
                    # Initialize with backtest return as fallback
                    final_return_for_grid = results['total_return_pct']
                    
                    # Run analysis immediately after each backtest if requested
                    if run_analysis:
                        tp_folder = f"{tp_r_val*100:.1f}%"
                        sl_folder = f"{sl_r_val*100:.1f}%"
                        add_buy_folder = f"add_buy_{current_add_buy_pct_val:.1f}pct"
                        target_directory = os.path.join("backtest_results", tf, tp_folder, sl_folder, add_buy_folder)
                        
                        logging.info(f"\n--- Running Portfolio Analysis for {tp_folder} TP, {sl_folder} SL, {current_add_buy_pct_val:.1f}% Add.Buy ---")
                        try:
                            success = analyze_single_add_buy_folder(target_directory, create_charts=create_position_charts)
                            if success:
                                # Try to extract the annual return from analysis results
                                try:
                                    results_path = os.path.join(target_directory, "portfolio_analysis_results.txt")
                                    if os.path.exists(results_path):
                                        with open(results_path, 'r', encoding='utf-8') as f:
                                            content = f.read()
                                            # Extract annual return from the file
                                            import re
                                            match = re.search(r'Annualized Return:\s+([-+]?\d*\.?\d+)%', content)
                                            if match:
                                                annual_return_pct = float(match.group(1))
                                                final_return_for_grid = annual_return_pct
                                                logging.info(f"Using portfolio analysis return: {annual_return_pct:.2f}% (vs backtest: {results['total_return_pct']:.2f}%)")
                                except Exception as e:
                                    logging.warning(f"Could not extract annual return from analysis: {e}")
                                
                                logging.info(f"✓ Portfolio analysis complete for TP={tp_folder}, SL={sl_folder}, Add.Buy={current_add_buy_pct_val:.1f}%")
                            else:
                                logging.warning(f"✗ Portfolio analysis failed for TP={tp_folder}, SL={sl_folder}, Add.Buy={current_add_buy_pct_val:.1f}%")
                        except Exception as e:
                            logging.error(f"Error during portfolio analysis: {e}")
                    else:
                        # If analysis is disabled, use backtest return for grid search
                        if tp_sl_grid_choice.startswith("y"):
                            logging.info(f"Portfolio analysis disabled - using backtest return: {results['total_return_pct']:.2f}%")
                    
                    # Store result for grid plotting
                    if tp_sl_grid_choice.startswith("y"):
                        grid_results_for_tp_sl.append((tp_r_val, sl_r_val, final_return_for_grid))
            
            if tp_sl_grid_choice.startswith("y") and grid_results_for_tp_sl:
                add_buy_folder_name_for_plot = f"add_buy_{current_add_buy_pct_val:.1f}pct"
                # Note: plot_grid_search_results save_path is the directory where the HTML file will be saved.
                # The results_dir inside run_backtesting is where individual backtest text files/charts are saved.
                # This plot dir is for the aggregated 3D TP/SL grid plots.
                tp_sl_grid_plot_dir = os.path.join("backtest_results", tf, "grid_plots", add_buy_folder_name_for_plot)
                os.makedirs(tp_sl_grid_plot_dir, exist_ok=True)
                plot_grid_search_results(grid_results_for_tp_sl, tf, tp_sl_grid_plot_dir, add_buy_val_for_title=current_add_buy_pct_val)
        
        # Clear cache after completing all grid searches to free memory
        clear_signals_cache()
        
        logging.info("\n" + "="*60)
        logging.info("All backtesting and analysis complete!")
        logging.info("Cache cleared to free memory.")
        logging.info("="*60)
        return

    logging.info("\n----- Immediate (One-Time) Analysis for All Timeframes -----\n")
    run_weekly_analysis()
    run_daily_analysis()

    schedule.every(1).hours.do(run_weekly_analysis)
    schedule.every(1).hours.do(run_daily_analysis)

    logging.info("Schedule set. Bot will keep running, sir...")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
