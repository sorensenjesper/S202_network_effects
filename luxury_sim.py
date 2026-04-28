import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# --- CONFIGURATION & STATE INITIALIZATION ---
st.set_page_config(layout="wide", page_title="Luxury Consignment Strategy")

if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=[
        'Month', 'Buyer_Marketing', 'Seller_Marketing', 'Commission', 'Cash', 
        'Inventory_Count', 'Items_Sold', 'New_Items_Inbound', 'Avg_Days_to_Sell', 'Net_Profit'
    ])
    # Initial Conditions
    st.session_state.cash = 2_000_000        # Higher startup capital for inventory ops
    st.session_state.inventory = 500         # Starting bags/watches
    st.session_state.active_buyers = 200     # Starting customer base
    st.session_state.reputation = 100.0      # Starts perfect (Trust Score)
    st.session_state.month = 0
    st.session_state.game_over = False
    st.session_state.debug_log = {}
# --- SIDEBAR: STUDENT DECISIONS ---
st.sidebar.header("Step 1: Strategic Decisions")

# 1. Commission Strategy (The Take Rate)
st.sidebar.subheader("Monetization")
commission_rate = st.sidebar.slider("Platform Commission (%)", 10, 60, 40, 
                                    help="High commission = More revenue per item, but fewer sellers.")

# 2. Authentication Protocol (The Trust Lever)
st.sidebar.subheader("Operations & Quality")
auth_spend_per_item = st.sidebar.slider("Authentication Cost per Item ($)", 10, 100, 30, 
                                        help="Low spend risks fakes slipping through.")

# 3. Marketing (Acquisition)
st.sidebar.subheader("Monthly Marketing Budget")
buyer_marketing = st.sidebar.number_input("Buyer Marketing ($)", 0, 200000, 20000, step=5000)
seller_marketing = st.sidebar.number_input("Consignor Marketing ($)", 0, 200000, 20000, step=5000)

# --- SIMULATION ENGINE ---
def run_month():
    # Current State
    inventory = st.session_state.inventory
    buyers = st.session_state.active_buyers
    reputation = st.session_state.reputation
    cash = st.session_state.cash
    
# --- 1. SUPPLY SIDE CALCS (THE AMPLIFIER MODEL) ---
    
    # A. The "Organic Engine" (Liquidity & Economics)
    # -----------------------------------------------
    # 1. Liquidity Signal:
    # If items sell in 30 days, sellers are neutral (1.0x). 
    # If they sell in 10 days, sellers love it (Max 2.0x).
    # If they sell in 120 days, sellers hate it (Min 0.2x).
    if not st.session_state.history.empty:
        prev_speed = st.session_state.history.iloc[-1]['Avg_Days_to_Sell']
    else:
        prev_speed = 60

    #liquidity_multiplier = np.clip(2.0 - (prev_speed / 60), 0.2, 2.0)
    liquidity_multiplier = np.clip(2.5 - (prev_speed / 30), 0.2, 2.0)
    # 2. Payout Signal:
    # If commission is 40%, attractiveness is standard (1.0).
    # If commission drops to 20%, attractiveness spikes (1.5x).
    # If commission goes to 60%, attractiveness tanks (0.5x).
    payout_multiplier = max(0.1, 2.0 - (commission_rate / 40))
    
    # 3. Base Organic Flow:
    # This is the "Word of Mouth" factor.
    # It scales based on current inventory size (larger platforms have more gravity).
    base_organic_flow = 110 + (inventory * 0.05)
    
    # B. The "Marketing Turbocharger"
    # -----------------------------------------------
    # Marketing amplifies the organic flow. 
    # Logic: $0 spend = 1.0x (No boost). $20k spend = ~2.0x (Double the flow).
    # We use log to prevent infinite linear scaling (diminishing returns).
    marketing_amplifier = 1.0 + np.log1p(seller_marketing / 10000)
    
    # C. Total Inbound Calculation
    # New items = (Base Demand * Liquidity * Payout) * Marketing Boost
    new_items_inbound = (base_organic_flow * liquidity_multiplier * payout_multiplier) * marketing_amplifier
    
    # Cost remains the same (Processing)
    processing_cost = new_items_inbound * auth_spend_per_item
    
    # --- 2. AUTHENTICATION CALCS ---  Must spend $30 to eliminate fakes.  Above $30 money is wasted.  Too simple? Should be nonlinear and never zero. 
    fake_probability = max(0, (30 - auth_spend_per_item) / 100)
    
    # --- 3. DEMAND SIDE CALCS ---
    trust_multiplier = reputation / 100
    variety_multiplier = np.log10(max(1, inventory + 10))
    
    # declines in reputation have very strong effects on effectiveness of buyer marketing
    # multiplier of buyers captures organic attrition when <1
    new_buyer_traffic = (buyers * 0.95) + (buyer_marketing / 100 * trust_multiplier)
    
    # Multiplier changed to 0.15 (was 0.5) - this throttles demand growth by affecting how many buyers purchase. 
    # So this means in the model what matters is number of buyers, their individual purchase propensities are constant. 
    # However variety increases the conversion rate as a log function of inventory; greater inventory means any given buyer is more likely to find something.
    conversion_rate = 0.15
    demand_volume = new_buyer_traffic * variety_multiplier * conversion_rate
    sold_items = min(inventory + new_items_inbound, demand_volume)
    
    # --- 4. FEEDBACK CALCS ---
    #fakes_sold = sold_items * fake_probability
    #reputation_hit = fakes_sold * 2 
    #new_reputation = max(0, min(100, reputation - reputation_hit + 1))

    # A. The Probability Curve (Quadratic)
    # Logic: Cutting spend a little bit is safer. Cutting a lot is dangerous.
    # If Spend < $30: Risk starts.
    # At $25 spend: Risk is ~2.7% (was 5% in linear model)
    # At $10 spend: Risk is ~44% (Massive danger)
    if auth_spend_per_item < 30:
        fake_probability = ((30 - auth_spend_per_item) / 30) ** 2
    else:
        fake_probability = 0
    
    # B. The Actual Fakes Sold
    fakes_sold = sold_items * fake_probability

    # C. The Reputation Hit (Rate-Based)
    # Logic: We punish the % of failures, not the raw count.
    # We add a 'sensitivity' multiplier (e.g., 300).
    # If 1% of goods are fake -> 0.01 * 300 = -3 points Trust (Manageable warning)
    # If 5% of goods are fake -> 0.05 * 300 = -15 points Trust (Crisis)
    if sold_items > 0:
        fake_rate = fakes_sold / sold_items
        reputation_hit = fake_rate * 300
    else:
        reputation_hit = 0
    
    new_reputation = max(0, min(100, reputation - reputation_hit + 0.5))

    if sold_items > 0:
        days_to_sell = (inventory / sold_items) * 30
    else:
        days_to_sell = 120
        
    final_inventory = max(0, inventory + new_items_inbound - sold_items)
    
    # --- 5. FINANCIALS ---
    avg_item_price = 500
    gross_revenue = sold_items * avg_item_price * (commission_rate / 100)
    fixed_costs = 25000 
    total_spend = buyer_marketing + seller_marketing + processing_cost + fixed_costs
    net_profit = gross_revenue - total_spend
    new_cash = cash + net_profit
    
    if new_cash <= 0:
        st.session_state.game_over = True

    # --- SAVE STATE ---
    st.session_state.month += 1
    st.session_state.cash = new_cash
    st.session_state.inventory = final_inventory
    st.session_state.active_buyers = new_buyer_traffic
    st.session_state.reputation = new_reputation
    
    new_row = {
        'Month': st.session_state.month,
        'Buyer_Marketing': buyer_marketing,
        'Seller_Marketing': seller_marketing,
        'Commission': commission_rate,
        'Cash': new_cash,
        'Inventory_Count': final_inventory,
        'Items_Sold': sold_items,
        'New_Items_Inbound': new_items_inbound,
        'Avg_Days_to_Sell': days_to_sell,
        'Net_Profit': net_profit
    }
    st.session_state.history.loc[len(st.session_state.history)] = new_row

    # --- CAPTURE DEBUG DATA ---
    st.session_state.debug_log = {
        "--- SUPPLY DRIVERS ---": "",
        "Prev Days to Sell": f"{prev_speed:.1f} days",
        "Liquidity Multiplier": f"{liquidity_multiplier:.2f}x (Impact of speed)",
        "Payout Score": f"{payout_multiplier:.2f} (Impact of commision)",
        "Marketing Pull": f"{marketing_amplifier:.1f} items",
        "Total Inbound": f"{new_items_inbound:.1f} items",
        
        "--- DEMAND DRIVERS ---": "",
        "Trust Multiplier": f"{trust_multiplier:.2f}x",
        "Variety Multiplier": f"{variety_multiplier:.2f}x (Log of Inventory)",
        "Raw Demand Volume": f"{demand_volume:.1f} bids",
        "Actual Sold": f"{sold_items:.1f} items",
        "New buyer traffic": f"{new_buyer_traffic:.1f} buyers",

        
        "--- RISKS ---": "",
        "Fake Probability": f"{fake_probability:.1%} per item",
        "Fakes Sold": f"{fakes_sold:.1f}",
        "Reputation Hit": f"-{reputation_hit:.1f} pts"
    }

# --- DASHBOARD UI ---
st.title("Luxury Strategy Sim: The Trust & Inventory Game")

# Create 5 columns for the new layout
col1, col2, col3, col4, col5 = st.columns(5)

# 1. Cash Balance
col1.metric("Cash Balance", f"${st.session_state.cash/1000000:.2f}M")

# 2. Last Month Profit
# We check if history exists; if not, show $0
last_profit = st.session_state.history.iloc[-1]['Net_Profit'] if not st.session_state.history.empty else 0
col2.metric("Last Month Profit", f"${last_profit:,.0f}")

# 3. Inventory Level
col3.metric("Inventory", f"{int(st.session_state.inventory):,} items")

# 4. Items Sold (New addition)
last_sold = st.session_state.history.iloc[-1]['Items_Sold'] if not st.session_state.history.empty else 0
col4.metric("Items Sold", f"{int(last_sold):,} items")

# 5. Trust Score
col5.metric("Trust Score", f"{st.session_state.reputation:.1f}/100")

if st.session_state.game_over:
    st.error("❌ BANKRUPTCY! You ran out of cash.")
else:
    if st.button("RUN NEXT MONTH ➡️", type="primary"):
        run_month()
        st.rerun()


# --- VISUALIZATION ---
if not st.session_state.history.empty:
    st.divider()

    # 1. Financial Health (Line Chart)
    st.subheader("Financial Performance (Net Profit)")
    c_fin = alt.Chart(st.session_state.history).mark_line(point=True).encode(
        # Fix: axis=alt.Axis(labelAngle=0) forces labels to stay horizontal
        x=alt.X('Month:O', title='Month', axis=alt.Axis(labelAngle=0)), 
        y='Net_Profit',
        tooltip=['Month', 'Net_Profit', 'Cash']
    ).interactive()
    st.altair_chart(c_fin, use_container_width=True)
    
    # 2. Supply Chain Balance (Grouped Bar Chart)
    st.subheader("Supply Chain Health")
    chart_data = st.session_state.history[['Month', 'Inventory_Count', 'Items_Sold', 'New_Items_Inbound']].melt('Month')
    
    c_inv = alt.Chart(chart_data).mark_bar().encode(
        # Fix: axis=alt.Axis(labelAngle=0) added here as well
        x=alt.X('Month:O', title='Month', axis=alt.Axis(labelAngle=0)), 
        y=alt.Y('value', title='Units'),
        color=alt.Color('variable', title="Metric"),
        xOffset='variable:N', 
        tooltip=['Month', 'variable', 'value']
    ).interactive()
    
    st.altair_chart(c_inv, use_container_width=True)
 

# --- DEBUG SECTION ---
#""" if st.session_state.debug_log:
#    with st.expander("🛠️ Open 'Glass Box' Debugger (Variable Values)"):
#        st.write("Below are the internal variables from the most recent calculation:")
#        st.json(st.session_state.debug_log) """
    
    # 3. Data Table
    st.divider()
    with st.expander("📊 View Detailed Financial Log"):
        styled_history = st.session_state.history.style.format({
            "Cash": "${:,.0f}",
            "Net_Profit": "${:,.0f}",
            "Reputation_Score": "{:.1f}",
            "Avg_Days_to_Sell": "{:.1f} days",
            "Inventory_Count": "{:,.0f}",
            "Items_Sold": "{:,.0f}",
            "New_Items_Inbound": "{:,.0f}",
            "Buyer_Marketing": "${:,.0f}",
            "Seller_Marketing": "${:,.0f}",
            "Commission": "{:,.0f} %"

        })
        st.dataframe(styled_history, use_container_width=True)

    
# 2. Liquidity Tracking
# st.subheader("Liquidity")
# st.line_chart(st.session_state.history.set_index('Month')['Liquidity_Multiplier'])
# st.caption("If Trust drops, buyers disappear. Trust drops when you cut Authentication Spend.")

