"""
generate_portfolio_data.py

Downloads market data for a randomly selected number of assets
from the master asset universe and generates all financial inputs
required for portfolio optimization.

Change only N_ASSETS below to control the experiment.

Outputs:
    data/Portfolio_Data.xlsx

Sheets:
    Asset_Data
    Prices
    Daily_Returns
    Covariance
"""

import os
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import yfinance as yf

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import *

from config.assets import (
    get_asset_list,
    get_asset_class_mapping,
)

from config.settings import (
    start_date,
    end_date,
    Portfolio_Data_File,
)

warnings.filterwarnings("ignore")

TRADING_DAYS = 252


# ================================================================
# EXPERIMENT CONFIGURATION
# ================================================================

# Number of assets to randomly select
N_ASSETS = 12

# Set to an integer for reproducibility.
# Set to None for a different random selection every run.
RANDOM_SEED = 42


# ================================================================
# TRANSACTION COST ASSUMPTIONS
# ================================================================

TRANSACTION_COST = {
    "Equity": 0.0010,
    "Bond": 0.0007,
    "Commodity": 0.0015,
    "International": 0.0018,
    "REIT": 0.0012,
}


# ================================================================
# RANDOM ASSET SELECTION
# ================================================================

def select_random_assets():

    all_assets = get_asset_list()

    if N_ASSETS > len(all_assets):
        raise ValueError(
            f"N_ASSETS={N_ASSETS}, but only "
            f"{len(all_assets)} assets are available."
        )

    rng = np.random.default_rng(RANDOM_SEED)

    # Randomly select N_ASSETS without replacement
    selected_assets = rng.choice(
        all_assets,
        size=N_ASSETS,
        replace=False,
    )

    # Randomly organize the selected assets
    selected_assets = rng.permutation(
        selected_assets
    ).tolist()

    print("\n==============================================")
    print("RANDOM ASSET SELECTION")
    print("==============================================")
    print(f"Total available assets : {len(all_assets)}")
    print(f"Number selected        : {N_ASSETS}")
    print(f"Random seed            : {RANDOM_SEED}")
    print("\nSelected asset order:")

    for i, ticker in enumerate(selected_assets, start=1):
        print(f"{i:2d}. {ticker}")

    print("==============================================\n")

    return selected_assets


# ================================================================
# DOWNLOAD HISTORICAL DATA
# ================================================================

def download_market_data(tickers):

    print(
        f"\nDownloading {len(tickers)} selected assets "
        "from Yahoo Finance..."
    )

    data = yf.download(
        tickers=tickers,
        start=start_date,
        end=end_date,
        auto_adjust=True,
        progress=True,
        group_by="column",
        threads=True,
    )

    prices = data["Close"].dropna(how="all")
    volume = data["Volume"].dropna(how="all")

    # Keep EXACTLY the selected asset order
    available = [
        ticker
        for ticker in tickers
        if ticker in prices.columns
    ]

    prices = prices[available]
    volume = volume[available]

    # Check that all requested assets were downloaded
    missing = [
        ticker
        for ticker in tickers
        if ticker not in prices.columns
    ]

    if missing:
        raise ValueError(
            f"Yahoo Finance data missing for: {missing}"
        )

    return prices, volume


# ================================================================
# DRAWDOWN
# ================================================================

def compute_max_drawdown(prices: pd.DataFrame):

    cumulative = prices.divide(
        prices.iloc[0]
    )

    rolling_max = cumulative.cummax()

    drawdown = (
        cumulative.divide(rolling_max) - 1
    )

    return drawdown.min().abs()


# ================================================================
# DIVIDEND YIELD
# ================================================================

def fetch_dividend_yield(ticker):

    try:

        info = yf.Ticker(ticker).info

        value = info.get("dividendYield")

        if value is None:
            return ticker, 0.0

        return ticker, float(value)

    except Exception:

        return ticker, 0.0


def download_dividend_yields(tickers):

    print("Downloading dividend yields...")

    yields = {}

    with ThreadPoolExecutor(
        max_workers=8
    ) as executor:

        for ticker, value in executor.map(
            fetch_dividend_yield,
            tickers,
        ):

            yields[ticker] = value

    return yields


# ================================================================
# STATISTICS
# ================================================================

def calculate_statistics(
    prices,
    volume,
    selected_assets,
):

    print("Calculating statistics...")

    # ------------------------------------------------------------
    # Preserve the exact random asset order
    # ------------------------------------------------------------

    prices = prices[selected_assets]

    volume = volume[selected_assets]

    # ------------------------------------------------------------
    # Daily returns
    # ------------------------------------------------------------

    returns = prices.pct_change().dropna()

    # ------------------------------------------------------------
    # Expected return
    # ------------------------------------------------------------

    expected_return = (
        (1 + returns.mean()) ** TRADING_DAYS
    ) - 1

    # ------------------------------------------------------------
    # Covariance
    # ------------------------------------------------------------

    covariance = (
        returns.cov() * TRADING_DAYS
    )

    # ------------------------------------------------------------
    # Volatility
    # ------------------------------------------------------------

    volatility = (
        returns.std()
        * np.sqrt(TRADING_DAYS)
    )

    # ------------------------------------------------------------
    # Drawdown
    # ------------------------------------------------------------

    drawdown = compute_max_drawdown(
        prices
    )

    # ------------------------------------------------------------
    # Average volume
    # ------------------------------------------------------------

    avg_volume = volume.mean()

    # ------------------------------------------------------------
    # Asset classes
    # ------------------------------------------------------------

    asset_classes = get_asset_class_mapping()

    # ------------------------------------------------------------
    # Dividend yields
    # ------------------------------------------------------------

    dividend = download_dividend_yields(
        selected_assets
    )

    # ------------------------------------------------------------
    # Asset data
    # ------------------------------------------------------------

    asset_data = pd.DataFrame({

        "Ticker":
            selected_assets,

        "AssetClass":
            [
                asset_classes[t]
                for t in selected_assets
            ],

        "ExpectedReturn":
            [
                expected_return[t]
                for t in selected_assets
            ],

        "DividendYield":
            [
                dividend[t]
                for t in selected_assets
            ],

        "MaxDrawdown":
            [
                drawdown[t]
                for t in selected_assets
            ],

        "TransactionCost":
            [
                TRANSACTION_COST[
                    asset_classes[t]
                ]
                for t in selected_assets
            ],

        "AnnualVolatility":
            [
                volatility[t]
                for t in selected_assets
            ],

        "AverageVolume":
            [
                avg_volume[t]
                for t in selected_assets
            ],
    })

    # IMPORTANT:
    # Do NOT sort Asset_Data by AssetClass here.
    #
    # The random order must remain identical across:
    #   Asset_Data
    #   Prices
    #   Daily_Returns
    #   Covariance
    #
    # This guarantees that μ, y, d, c and Σ all refer
    # to the same asset index.

    covariance = covariance.loc[
        selected_assets,
        selected_assets,
    ]

    returns = returns[
        selected_assets
    ]

    prices = prices[
        selected_assets
    ]

    return (
        asset_data,
        prices,
        returns,
        covariance,
    )


# ================================================================
# SAVE EXCEL
# ================================================================

def save_excel(
    asset_data,
    prices,
    returns,
    covariance,
):

    os.makedirs(
        os.path.dirname(
            Portfolio_Data_File
        ),
        exist_ok=True,
    )

    with pd.ExcelWriter(
        Portfolio_Data_File,
        engine="openpyxl",
    ) as writer:

        asset_data.to_excel(
            writer,
            sheet_name="Asset_Data",
            index=False,
        )

        prices.to_excel(
            writer,
            sheet_name="Prices",
        )

        returns.to_excel(
            writer,
            sheet_name="Daily_Returns",
        )

        covariance.to_excel(
            writer,
            sheet_name="Covariance",
        )

    print(
        f"\nSaved to {Portfolio_Data_File}"
    )


# ================================================================
# MAIN
# ================================================================

def main():

    # ------------------------------------------------------------
    # 1. Randomly select assets
    # ------------------------------------------------------------

    selected_assets = (
        select_random_assets()
    )

    # ------------------------------------------------------------
    # 2. Download only selected assets
    # ------------------------------------------------------------

    prices, volume = (
        download_market_data(
            selected_assets
        )
    )

    # ------------------------------------------------------------
    # 3. Calculate financial inputs
    # ------------------------------------------------------------

    (
        asset_data,
        prices,
        returns,
        covariance,
    ) = calculate_statistics(
        prices,
        volume,
        selected_assets,
    )

    # ------------------------------------------------------------
    # 4. Save Portfolio_Data.xlsx
    # ------------------------------------------------------------

    save_excel(
        asset_data,
        prices,
        returns,
        covariance,
    )

    # ------------------------------------------------------------
    # 5. Final verification
    # ------------------------------------------------------------

    print("\n==============================================")
    print("DATA GENERATION COMPLETE")
    print("==============================================")
    print(
        f"Number of assets : "
        f"{len(asset_data)}"
    )
    print(
        f"Covariance shape : "
        f"{covariance.shape}"
    )

    print("\nFinal asset order:")

    print(
        asset_data["Ticker"].tolist()
    )

    print("==============================================\n")


if __name__ == "__main__":
    main()