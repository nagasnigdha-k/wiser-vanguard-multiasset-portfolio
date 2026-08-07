"""
assets.py
Asset Configuration

This file defines the assets used for multi-asset portfolio optimization.

Each asset contains:
    - asset_class : Broad asset category
    - group       : Sub-category used for allocation constraints


The helper functions automatically generate:
    - asset list
    - asset index mapping
    - asset class mapping
    - group mapping
    - asset class groups
    - group index sets

"""

# =============================================================================
# MASTER ASSET UNIVERSE (20 Assets)
# =============================================================================

ASSET_INFO = {

    # -------------------------------------------------------------------------
    # EQUITY (6)
    # -------------------------------------------------------------------------

    "SPY": {
        "asset_class": "Equity",
        "group": "Broad Market"
    },

    "QQQ": {
        "asset_class": "Equity",
        "group": "Technology"
    },

    "XLF": {
        "asset_class": "Equity",
        "group": "Financials"
    },

    "XLK": {
        "asset_class": "Equity",
        "group": "Technology"
    },

    "XLV": {
        "asset_class": "Equity",
        "group": "Healthcare"
    },

    "XLE": {
        "asset_class": "Equity",
        "group": "Energy"
    },

    # -------------------------------------------------------------------------
    # BONDS (4)
    # -------------------------------------------------------------------------

    "BND": {
        "asset_class": "Bond",
        "group": "Aggregate Bond"
    },

    "TLT": {
        "asset_class": "Bond",
        "group": "Treasury"
    },

    "LQD": {
        "asset_class": "Bond",
        "group": "Corporate Bond"
    },

    "HYG": {
        "asset_class": "Bond",
        "group": "High Yield"
    },

    # -------------------------------------------------------------------------
    # COMMODITIES (4)
    # -------------------------------------------------------------------------

    "GLD": {
        "asset_class": "Commodity",
        "group": "Gold"
    },

    "SLV": {
        "asset_class": "Commodity",
        "group": "Silver"
    },

    "USO": {
        "asset_class": "Commodity",
        "group": "Oil"
    },

    "DBC": {
        "asset_class": "Commodity",
        "group": "Diversified Commodity"
    },

    # -------------------------------------------------------------------------
    # INTERNATIONAL (3)
    # -------------------------------------------------------------------------

    "VEA": {
        "asset_class": "International",
        "group": "Developed Markets"
    },

    "EEM": {
        "asset_class": "International",
        "group": "Emerging Markets"
    },

    "INDA": {
        "asset_class": "International",
        "group": "India"
    },

    # -------------------------------------------------------------------------
    # REITS (3)
    # -------------------------------------------------------------------------

    "VNQ": {
        "asset_class": "REIT",
        "group": "Real Estate"
    },

    "XLRE": {
        "asset_class": "REIT",
        "group": "Real Estate"
    },

    "REET": {
        "asset_class": "REIT",
        "group": "Global Real Estate"
    }

}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_asset_list():
    """
    Returns an ordered list of all assets.
    """

    return list(ASSET_INFO.keys())


def get_asset_index_mapping():
    """
    Returns

    {
        'SPY':0,
        'QQQ':1,
        ...
    }
    """

    return {
        ticker: idx
        for idx, ticker in enumerate(get_asset_list())
    }


def get_index_asset_mapping():
    """
    Returns

    {
        0:'SPY',
        1:'QQQ',
        ...
    }
    """

    return {
        idx: ticker
        for idx, ticker in enumerate(get_asset_list())
    }


def get_asset_class_mapping():
    """
    Returns

    {
        'SPY':'Equity',
        ...
    }
    """

    return {
        ticker: info["asset_class"]
        for ticker, info in ASSET_INFO.items()
    }


def get_group_mapping():
    """
    Returns

    {
        'QQQ':'Technology',
        'TLT':'Treasury',
        ...
    }
    """

    return {
        ticker: info["group"]
        for ticker, info in ASSET_INFO.items()
    }


def get_region_mapping():
    """
    Returns

    {
        'SPY':'US',
        ...
    }
    """

    return {
        ticker: info["region"]
        for ticker, info in ASSET_INFO.items()
    }


def get_asset_class_groups():
    """
    Returns

    {
        'Equity':['SPY','QQQ',...],
        'Bond':['BND','TLT',...],
        ...
    }
    """

    groups = {}

    for ticker, info in ASSET_INFO.items():

        cls = info["asset_class"]

        groups.setdefault(cls, []).append(ticker)

    return groups


def get_group_groups():
    """
    Returns

    {
        'Technology':['QQQ','XLK'],
        'Treasury':['TLT'],
        'Gold':['GLD'],
        ...
    }
    """

    groups = {}

    for ticker, info in ASSET_INFO.items():

        group = info["group"]

        groups.setdefault(group, []).append(ticker)

    return groups


def get_asset_class_index_sets():
    """
    Returns

    {
        'Equity':[0,1,2,3,4,5],
        'Bond':[6,7,8,9],
        ...
    }

    Useful for multi-asset allocation constraints.
    """

    asset_index = get_asset_index_mapping()

    class_indices = {}

    for ticker, info in ASSET_INFO.items():

        cls = info["asset_class"]

        class_indices.setdefault(cls, []).append(
            asset_index[ticker]
        )

    return class_indices


def get_group_index_sets():
    """
    Returns

    {
        'Technology':[1,3],
        'Financials':[2],
        'Treasury':[7],
        'Gold':[10],
        ...
    }

    These index sets are used directly in
    mathematical optimization constraints.
    """

    asset_index = get_asset_index_mapping()

    group_indices = {}

    for ticker, info in ASSET_INFO.items():

        group = info["group"]

        group_indices.setdefault(group, []).append(
            asset_index[ticker]
        )

    return group_indices


def get_assets_by_class(asset_class):
    """
    Returns all assets belonging to an asset class.
    """

    return get_asset_class_groups().get(asset_class, [])


def get_assets_by_group(group):
    """
    Returns all assets belonging to a group.
    """

    return get_group_groups().get(group, [])