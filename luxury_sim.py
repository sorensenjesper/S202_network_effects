import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# --- CONFIGURATION & STATE INITIALIZATION ---
st.set_page_config(layout="wide", page_title="Luxury Consignment Strategy")

# 1. Global Fund State (Persists across resets)
if 'round_number' not in st.session_state:
    st.session_state.round_number = 1
    st.session_state.cash = 10_000_000  # Staked with $10M total for all experiments
    st.session_state.starting_cash_this_round = 10_000_000
    st.session_state.total_months_played = 0  # NEW: Global clock
    st.session_state.max_months = 60          # NEW: Time limit

# 2. Round-Specific State (Resets each experiment)
if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=[
        'Month', 'Buyer_Marketing', 'Seller_Marketing', 'Commission', 'Cash', 
        'Inventory_Count', 'Items_Sold', 'New_Items_Inbound', 'Avg_Days_to_Sell', 'Net_Profit'
    ])
    st.session_state.inventory = 500         
    st.session_state.active_buyers = 200     
    st.session_state.reputation = 100.0      
    st.session_state.month = 0
    st.session_state.game_over = False
    st.session_state.debug_log = {}

# Function to trigger a new experiment
def start_new_round():
    st.session_state.round_number += 1
    st.session_state.starting_cash_this_round = st.session_state.cash
    
    # Reset operational variables
    st.session_state.inventory = 500
    st.session_state.active_buyers = 200
    st.session_state.reputation = 100.0
    st.session_state.month = 0
    st.session_state.game_over = False
    st.session_state.history = pd.DataFrame(columns=[
        'Month', 'Buyer_Marketing', 'Seller_Marketing', 'Commission', 'Cash', 
        'Inventory_Count', 'Items_Sold', 'New_Items_Inbound', 'Avg_Days_to_Sell', 'Net_Profit'
    ])
    st.session_state.debug_log = {}

# --- SIDEBAR: STUDENT DECISIONS ---
st.sidebar.header("Strategic Decisions")

# 1. Commission Strategy (The Take Rate)
st.sidebar.subheader("Monetization")
commission_rate = st.sidebar.slider("Platform Commission (%)", 10, 90, 50, 
                                    help="High commission = More revenue per item, but fewer sellers.")

# 2. Authentication Protocol (The Trust Lever)
st.sidebar.subheader("Operations & Quality")
auth_spend_per_item = st.sidebar.slider("Authentication Cost per Item ($)", 10, 100, 30, 
                                        help="Low spend risks fakes slipping through.")

# 3. Marketing (Acquisition)
st.sidebar.subheader("Monthly Marketing Budget")
buyer_marketing = st.sidebar.number_input("Buyer Marketing ($)", 0, 200000, 10000, step=5000)
seller_marketing = st.sidebar.number_input("Seller Marketing ($)", 0, 200000, 10000, step=5000)

# --- SIDEBAR: NEW EXPERIMENT BUTTON ---
st.sidebar.divider()
if st.sidebar.button("🔄 Start New Experiment", use_container_width=True):
    start_new_round()
    st.rerun()

# --- SIMULATION ENGINE ---
def run_month():
    # Current State
    inventory = st.session_state.inventory
    buyers = st.session_state.active_buyers
    reputation = st.session_state.reputation
    cash = st.session_state.cash
    
# --- 1. SUPPLY SIDE CALCS (THE STABLE MODEL) ---
    if not st.session_state.history.empty:
        prev_speed = st.session_state.history.iloc[-1]['Avg_Days_to_Sell']
    else:
        prev_speed = 60

    # Smooth Liquidity (30 days is optimal, 90 days is slow)
    liquidity_multiplier = np.clip(2.5 - (prev_speed / 90), 0.2, 2.0)
    
    # Standard Payout (Calibrated for a trap)
    # At 20% Comm: Multiplier is 1.3x (Boost for building)
    # At 40% Comm: Multiplier is 0.5x (Harvest phase - speed cancels this penalty)
    # At 50% Comm: Multiplier is 0.1x (Absolute chokehold - default trap)
    payout_multiplier = max(0.1, 2.1 - (commission_rate / 25))
    # Standard Payout
    #payout_multiplier = max(0.1, 2.0 - (commission_rate / 40))
    
    # The Original Generous Base Flow
    base_organic_flow = 110 + (inventory * 0.05)
    
    # The Original Marketing Turbocharger
    marketing_amplifier = 1.0 + np.log1p(seller_marketing / 10000)
    
    # C. Total Inbound Calculation
    new_items_inbound = (base_organic_flow * liquidity_multiplier * payout_multiplier) * marketing_amplifier
    processing_cost = new_items_inbound * auth_spend_per_item


# --- 2. AUTHENTICATION CALCS ---
    if auth_spend_per_item < 30:
        fake_probability = ((30 - auth_spend_per_item) / 30) ** 2
    else:
        fake_probability = 0
    
    # --- 3. DEMAND SIDE CALCS ---
    trust_multiplier = reputation / 100
    variety_multiplier = np.log10(max(1, inventory + 10))
    
    new_buyer_traffic = (buyers * 0.95) + (buyer_marketing / 100 * trust_multiplier)
    
    conversion_rate = 0.15
    demand_volume = new_buyer_traffic * variety_multiplier * conversion_rate
    sold_items = min(inventory + new_items_inbound, demand_volume)
    
    # --- 4. FEEDBACK CALCS (WITH DAMPENER) ---
    fakes_sold = sold_items * fake_probability

    if sold_items > 0:
        fake_rate = fakes_sold / sold_items
        reputation_hit = fake_rate * 300
    else:
        reputation_hit = 0
    
    new_reputation = max(0, min(100, reputation - reputation_hit + 0.5))

    # THE DAMPENER: Smooth out the velocity so sellers don't panic instantly
    if sold_items > 0:
        current_speed = (inventory / sold_items) * 30
    else:
        current_speed = 120
        
    # Blend current speed with previous speed (50/50 Trailing Average)
    days_to_sell = (current_speed * 0.5) + (prev_speed * 0.5)
        
    final_inventory = max(0, inventory + new_items_inbound - sold_items)
    
    # --- 5. FINANCIALS ---
    avg_item_price = 500
    gross_revenue = sold_items * avg_item_price * (commission_rate / 100)
    fixed_costs = 25000 
    total_spend = buyer_marketing + seller_marketing + processing_cost + fixed_costs
    net_profit = gross_revenue - total_spend
    new_cash = cash + net_profit
    
    # Check for Bankruptcy OR Time Out
    st.session_state.total_months_played += 1
    if new_cash <= 0:
        st.session_state.game_over = "bankrupt"
    elif st.session_state.total_months_played >= st.session_state.max_months:
        st.session_state.game_over = "timeout"

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
st.title(f"Luxury Consignment Sim (Experiment {st.session_state.round_number})")

# TIER 1: GLOBAL FUND METRICS
st.markdown("### 🏦 VC Fund Performance")
fc1, fc2 = st.columns(2)

fc1.metric("Total Fund Cash Remaining", f"${st.session_state.cash/1000000:.2f}M")

# Calculate how much money they have made/lost in THIS specific attempt
round_pnl = st.session_state.cash - st.session_state.starting_cash_this_round
fc2.metric("P&L for Current Experiment", f"${round_pnl:,.0f}")

st.divider()

# TIER 2: MONTHLY OPERATIONAL METRICS
st.markdown("### 📊 Operational Dashboard (Current Month)")
col1, col2, col3, col4 = st.columns(4)

# Last Month Profit
last_profit = st.session_state.history.iloc[-1]['Net_Profit'] if not st.session_state.history.empty else 0
col1.metric("Last Month Profit", f"${last_profit:,.0f}")

# Inventory Level
#col2.metric("Inventory", f"{int(st.session_state.inventory):,} items")
col2.metric("Inventory", f"{st.session_state.inventory:.0f} items")

# Items Sold
last_sold = st.session_state.history.iloc[-1]['Items_Sold'] if not st.session_state.history.empty else 0
#col3.metric("Items Sold", f"{int(last_sold):,} items")
col3.metric("Items Sold", f"{last_sold:.0f} items")

# Trust Score
col4.metric("Trust Score", f"{st.session_state.reputation:.0f}/100")

# Run Button & Game Over Logic
st.write("") 

# Show the clock
st.progress(st.session_state.total_months_played / st.session_state.max_months, 
            text=f"Fund Time Remaining: {st.session_state.max_months - st.session_state.total_months_played} months")

if st.session_state.game_over == "bankrupt":
    st.error("❌ BANKRUPTCY! The fund is out of money.")
elif st.session_state.game_over == "timeout":
    st.success(f"🏁 TIME'S UP! The VC Fund has closed. Your Final Score (Remaining Cash): ${st.session_state.cash/1000000:.2f}M")
else:
    if st.button("RUN NEXT MONTH ➡️", type="primary"):
        run_month()
        st.rerun()

# # Run Button & Game Over Logic
# st.write("") # small spacing
# if st.session_state.game_over:
#     st.error("❌ BANKRUPTCY! The fund is out of money. Please refresh your browser to reset the entire simulation.")
# else:
#     if st.button("RUN NEXT MONTH ➡️", type="primary"):
#         run_month()
#         st.rerun()

# --- VISUALIZATION ---
if not st.session_state.history.empty:
    st.divider()

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

        
    # 1. Financial Health (Line Chart)
    st.subheader("Financial Performance (Net Profit)")
    c_fin = alt.Chart(st.session_state.history).mark_line(point=True).encode(
        x=alt.X('Month:O', title='Month', axis=alt.Axis(labelAngle=0)), 
        y='Net_Profit',
        tooltip=['Month', 'Net_Profit', 'Cash']
    ).interactive()
    st.altair_chart(c_fin, use_container_width=True)
    
    # 2. Supply Chain Balance (Grouped Bar Chart)
    st.subheader("Supply Chain Health")
    chart_data = st.session_state.history[['Month', 'Inventory_Count', 'Items_Sold', 'New_Items_Inbound']].melt('Month')
    
    c_inv = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X('Month:O', title='Month', axis=alt.Axis(labelAngle=0)), 
        y=alt.Y('value', title='Units'),
        color=alt.Color('variable', title="Metric"),
        xOffset='variable:N', 
        tooltip=['Month', 'variable', 'value']
    ).interactive()
    
    st.altair_chart(c_inv, use_container_width=True)
 
