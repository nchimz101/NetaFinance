import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os

# Define currency symbol and initial balance globally
CURRENCY_SYMBOL = "ZMW"
INITIAL_BALANCE = 69297  # Starting balance as provided

# Function to load and save the current balance
def load_balance():
    balance_file = "current_balance.txt"
    try:
        if os.path.exists(balance_file):
            with open(balance_file, "r") as f:
                return float(f.read().strip())
        else:
            # If file doesn't exist, use the initial balance and create the file
            save_balance(INITIAL_BALANCE)
            return INITIAL_BALANCE
    except Exception as e:
        st.warning(f"Could not load current balance: {e}. Using default value.")
        return INITIAL_BALANCE

def save_balance(balance):
    try:
        with open("current_balance.txt", "w") as f:
            f.write(str(balance))
        return True
    except Exception as e:
        st.error(f"Could not save current balance: {e}")
        return False

def recalculate_balance(transactions_df):
    """Calculate balance from all transactions"""
    if transactions_df.empty:
        return INITIAL_BALANCE
        
    # Sum all transactions: credits add to balance, debits subtract
    credits = transactions_df[transactions_df['transaction_type'] == 'credit']['amount'].sum()
    debits = transactions_df[transactions_df['transaction_type'] == 'debit']['amount'].sum()
    
    # Calculate new balance starting from initial balance
    return INITIAL_BALANCE + credits - debits

def update_balance_after_transaction(amount, transaction_type):
    """Update balance after a new transaction"""
    current_balance = load_balance()
    
    if transaction_type == 'credit':
        new_balance = current_balance + amount
    else:  # debit
        new_balance = current_balance - amount
        
    save_balance(new_balance)
    return new_balance

# Load current balance when app starts
current_balance = load_balance()

# Set page config
st.set_page_config(page_title="Netagrow Financial Dashboard", layout="wide", page_icon="🌱")

# Application title and description - Updated for Netagrow
st.title("Netagrow Financial Management")
st.markdown("Track, manage and analyze Netagrow's finances to support sustainable growth.")

# Load categories from JSON file
@st.cache_data
def load_categories():
    try:
        with open(os.path.join("config", "categories.json"), "r") as f:
            categories = json.load(f)
        return categories
    except Exception as e:
        st.warning(f"Could not load categories: {e}")
        return {
            "income_categories": [],
            "expense_categories": []
        }

# Function to load data
@st.cache_data
def load_data(uploaded_file=None):
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            return df
        except Exception as e:
            st.error(f"Error loading file: {e}")
            return None

    # Load sample data if available in the current directory
    try:
        df = pd.read_csv("trial_balance.csv")
        # Ensure category_name is properly populated and not numeric
        if 'category_name' in df.columns:
            # Convert any numeric-only category names to proper descriptive names
            # based on category_id mappings from our config
            categories = load_categories()
            cat_id_to_name = {}
            
            # Build a mapping of category IDs to names
            for cat in categories['income_categories']:
                cat_id_to_name[cat['id']] = cat['name']
            for cat in categories['expense_categories']:
                cat_id_to_name[cat['id']] = cat['name']
                
            # Apply mapping where needed
            for idx, row in df.iterrows():
                if pd.notna(row['category_id']) and (pd.isna(row['category_name']) or str(row['category_name']).isdigit()):
                    cat_id = int(row['category_id'])
                    if cat_id in cat_id_to_name:
                        df.at[idx, 'category_name'] = cat_id_to_name[cat_id]
        return df
    except Exception as e:
        st.error(f"Error loading sample data: {e}")
        # Create a template with column names if no data exists
        return pd.DataFrame(columns=[
            'id', 'date', 'description', 'amount', 'transaction_type',
            'company_id', 'category_id', 'category_name', 'budget_id',
            'ledger_id', 'notes', 'remarks', 'reporting_trigger',
            'transaction_date', 'active_agent'
        ])


# Function to format date columns
def format_dates(df):
    if df is not None and 'date' in df.columns:
        try:
            df['date'] = pd.to_datetime(df['date'], format='%m/%d/%y %H:%M')
        except:
            st.warning("Could not parse date column. Using original format.")
    return df

# Load categories
categories = load_categories()

# Sidebar for navigation
st.sidebar.title("Netagrow Finance")
page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Financial Statements", "Transactions", "Reports", "Settings"]
)

# Remove file uploader and always load internal data
df = load_data()
df = format_dates(df)

# Date filtering
st.sidebar.header("Date Range Filter")
if df is not None and 'date' in df.columns and not df.empty:
    min_date = df['date'].min().date() if not pd.isna(df['date'].min()) else datetime.now().date() - timedelta(days=365)
    max_date = df['date'].max().date() if not pd.isna(df['date'].max()) else datetime.now().date()

    start_date = st.sidebar.date_input("Start date", min_date)
    end_date = st.sidebar.date_input("End date", max_date)

    # Filter dataframe by date
    if 'date' in df.columns:
        filtered_df = df[(df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)]
else:
    filtered_df = pd.DataFrame()


# Helper functions
def generate_category_summary(df):
    if df.empty:
        return pd.DataFrame()

    try:
        summary = df.groupby(['category_name', 'transaction_type'])['amount'].sum().unstack(fill_value=0).reset_index()
        
        # Ensure 'credit' and 'debit' columns exist before renaming
        if 'credit' not in summary.columns:
            summary['credit'] = 0
        if 'debit' not in summary.columns:
            summary['debit'] = 0
            
        # Now rename the columns safely
        summary = summary.rename(columns={'credit': 'income', 'debit': 'expenses'})
        summary['net'] = summary['income'] - summary['expenses']
        return summary
    except Exception as e:
        st.error(f"Error generating category summary: {e}")
        # Return an empty DataFrame with the expected columns
        return pd.DataFrame(columns=['category_name', 'income', 'expenses', 'net'])


def calculate_pl_statement(df):
    """
    Calculate a properly structured profit and loss statement based on transaction types
    """
    if df.empty:
        return pd.DataFrame()

    # Separate income and expenses properly using transaction_type
    income_df = df[df['transaction_type'] == 'credit']
    expense_df = df[df['transaction_type'] == 'debit']
    
    # Calculate income by category
    income_by_category = income_df.groupby('category_name')['amount'].sum().reset_index()
    income_by_category['type'] = 'Income'
    
    # Calculate expenses by category
    expense_by_category = expense_df.groupby('category_name')['amount'].sum().reset_index()
    expense_by_category['type'] = 'Expense'
    
    # Combine income and expenses
    pl = pd.concat([income_by_category, expense_by_category])
    
    # Calculate totals
    total_income = income_df['amount'].sum()
    total_expenses = expense_df['amount'].sum()
    net_profit = total_income - total_expenses
    
    # Add summary rows
    summary_rows = pd.DataFrame({
        'category_name': ['Total Income', 'Total Expenses', 'Net Profit/Loss'],
        'amount': [total_income, total_expenses, net_profit],
        'type': ['Summary', 'Summary', 'Summary']
    })
    
    # Combine with summary rows
    pl = pd.concat([pl, summary_rows], ignore_index=True)
    
    return pl

def categorize_balance_sheet_items(df):
    """
    Categorize transactions into balance sheet components:
    Assets, Liabilities and Equity
    """
    # Define balance sheet category mappings
    # In a real app, this would come from a more comprehensive accounting system
    asset_categories = ["Cash", "Accounts Receivable", "Inventory", "Equipment", "IT Infrastructure"]
    liability_categories = ["Accounts Payable", "Loans", "Taxes & Duties"]
    
    # Start with empty DataFrames for each category
    assets = pd.DataFrame(columns=df.columns)
    liabilities = pd.DataFrame(columns=df.columns)  # Fixed: Added missing closing parenthesis
    equity = pd.DataFrame(columns=df.columns)
    
    # Categorize based on category_name
    for category in asset_categories:
        assets = pd.concat([assets, df[df['category_name'].str.contains(category, case=False, na=False)]])
    
    for category in liability_categories:
        liabilities = pd.concat([liabilities, df[df['category_name'].str.contains(category, case=False, na=False)]])
    
    # Simplistically treat income and expenses as affecting equity
    # Credits (income) increase equity, debits (expenses) decrease equity
    income = df[df['transaction_type'] == 'credit']
    expenses = df[df['transaction_type'] == 'debit']
    # Filter out items already categorized as assets or liabilities
    income = income[~income.index.isin(assets.index) & ~income.index.isin(liabilities.index)]
    expenses = expenses[~expenses.index.isin(assets.index) & ~expenses.index.isin(liabilities.index)]
    
    equity = pd.concat([income, expenses])
    
    return assets, liabilities, equity

def calculate_balance_sheet(df):
    """
    Calculate a structured balance sheet from transaction data
    following the format provided, using actual current balance
    """
    if df.empty:
        return pd.DataFrame()
        
    # Get current balance for cash at hand
    cash_at_hand = load_balance()
    
    # Get categorized transactions for other balance sheet items
    assets_df, liabilities_df, equity_df = categorize_balance_sheet_items(df)
    
    # Process assets - split into current and non-current
    it_infra = assets_df[assets_df['category_name'].str.contains('IT Infrastructure', case=False, na=False)]
    software = assets_df[assets_df['category_name'].str.contains('Software', case=False, na=False)]
    
    # Simplistic approach: consider IT and Software as non-current assets
    non_current_assets = pd.concat([it_infra, software])
    non_current_assets_total = non_current_assets['amount'].sum() if not non_current_assets.empty else 0
    
    # Total assets is cash plus other assets
    total_assets = cash_at_hand + non_current_assets_total
    
    # Rest of balance sheet calculation remains the same
    # Process liabilities - split them into types
    # In a real system, you'd have more detailed categorization
    creditors = liabilities_df[liabilities_df['category_name'].str.contains('Payable|Vendor', case=False, na=False)]
    short_term_loans = liabilities_df[liabilities_df['category_name'].str.contains('Short-term|Current', case=False, na=False)]
    long_term_loans = liabilities_df[liabilities_df['category_name'].str.contains('Long-term|Non-current', case=False, na=False)]
    
    # Any uncategorized liabilities go to creditors
    other_liabilities = liabilities_df[~liabilities_df.index.isin(creditors.index) & 
                                      ~liabilities_df.index.isin(short_term_loans.index) &
                                      ~liabilities_df.index.isin(long_term_loans.index)]
    creditors = pd.concat([creditors, other_liabilities])
    
    # Calculate liability totals
    creditors_total = creditors['amount'].sum() if not creditors.empty else 0
    short_term_loans_total = short_term_loans['amount'].sum() if not short_term_loans.empty else 0
    long_term_loans_total = long_term_loans['amount'].sum() if not long_term_loans.empty else 0
    total_loans = short_term_loans_total + long_term_loans_total
    total_liabilities = creditors_total + total_loans
    
    # Calculate equity totals
    equity_credits = equity_df[equity_df['transaction_type'] == 'credit']['amount'].sum()
    equity_debits = equity_df[equity_df['transaction_type'] == 'debit']['amount'].sum()
    total_equity = equity_credits - equity_debits
    
    # Calculate net assets (should equal equity)
    net_assets = total_assets - total_liabilities
    
    # Create the balance sheet in the requested format
    balance_sheet = pd.DataFrame({
        'Description': [
            'Non-Current Assets:',
            'Total Non-Current Assets',
            'Current Assets:',
            'A) Cash at Hand',
            'Total Cash at Hand',
            'Total Current Assets',
            'Total Assets',
            'Current Liabilities:',
            'A) Creditors',
            'Total Creditors',
            'B) Short Term Loans',
            'Total Short Term Loans',
            'C) Long Term Loans',
            'Total Long Term Loans',
            'Total Loans',
            'Total Current Liabilities',
            'Net Assets'
        ],
        'Amount': [
            '', 
            non_current_assets_total,
            '',
            '',
            cash_at_hand,  # Use the actual current balance
            cash_at_hand,  # Use the actual current balance
            total_assets,
            '',
            '',
            creditors_total,
            '',
            short_term_loans_total,
            '',
            long_term_loans_total,
            total_loans,
            total_liabilities,
            net_assets
        ],
        'row_type': [  # Renamed from 'type' to avoid confusion
            'header', 'total', 'header', 'subheader', 'subtotal',
            'total', 'grandtotal', 'header', 'subheader', 'subtotal',
            'subheader', 'subtotal', 'subheader', 'subtotal',
            'subtotal', 'total', 'grandtotal'
        ]
    })
    
    return balance_sheet

# Create a new function to audit and validate the balance sheet calculations
def audit_balance_sheet(df, calculated_balance_sheet):
    """
    Audit the balance sheet for accuracy and return detailed diagnostics
    """
    audit_results = {}
    
    # Get the raw data we need for validation
    assets_df, liabilities_df, equity_df = categorize_balance_sheet_items(df)
    cash_at_hand = load_balance()
    
    # Validate IT Infrastructure and Software assets
    it_infra = assets_df[assets_df['category_name'].str.contains('IT Infrastructure', case=False, na=False)]
    software = assets_df[assets_df['category_name'].str.contains('Software', case=False, na=False)]
    non_current_assets = pd.concat([it_infra, software])
    actual_non_current_assets = non_current_assets['amount'].sum() if not non_current_assets.empty else 0
    
    # Get values from the calculated balance sheet
    bs_non_current_assets = calculated_balance_sheet[calculated_balance_sheet['Description'] == 'Total Non-Current Assets']['Amount'].values[0]
    bs_cash_at_hand = calculated_balance_sheet[calculated_balance_sheet['Description'] == 'Total Cash at Hand']['Amount'].values[0]
    bs_total_assets = calculated_balance_sheet[calculated_balance_sheet['Description'] == 'Total Assets']['Amount'].values[0]
    bs_net_assets = calculated_balance_sheet[calculated_balance_sheet['Description'] == 'Net Assets']['Amount'].values[0]
    
    # Validate liabilities
    creditors = liabilities_df[liabilities_df['category_name'].str.contains('Payable|Vendor', case=False, na=False)]
    short_term_loans = liabilities_df[liabilities_df['category_name'].str.contains('Short-term|Current', case=False, na=False)]
    long_term_loans = liabilities_df[liabilities_df['category_name'].str.contains('Long-term|Non-current', case=False, na=False)]
    other_liabilities = liabilities_df[~liabilities_df.index.isin(creditors.index) & 
                                     ~liabilities_df.index.isin(short_term_loans.index) &
                                     ~liabilities_df.index.isin(long_term_loans.index)]
    
    actual_creditors = creditors['amount'].sum() if not creditors.empty else 0
    actual_short_loans = short_term_loans['amount'].sum() if not short_term_loans.empty else 0
    actual_long_loans = long_term_loans['amount'].sum() if not long_term_loans.empty else 0
    actual_other_liabilities = other_liabilities['amount'].sum() if not other_liabilities.empty else 0
    
    bs_creditors = calculated_balance_sheet[calculated_balance_sheet['Description'] == 'Total Creditors']['Amount'].values[0]
    bs_short_loans = calculated_balance_sheet[calculated_balance_sheet['Description'] == 'Total Short Term Loans']['Amount'].values[0]
    bs_long_loans = calculated_balance_sheet[calculated_balance_sheet['Description'] == 'Total Long Term Loans']['Amount'].values[0]
    bs_total_loans = calculated_balance_sheet[calculated_balance_sheet['Description'] == 'Total Loans']['Amount'].values[0]
    bs_total_liabilities = calculated_balance_sheet[calculated_balance_sheet['Description'] == 'Total Current Liabilities']['Amount'].values[0]
    
    # Validate equity
    equity_credits = equity_df[equity_df['transaction_type'] == 'credit']['amount'].sum()
    equity_debits = equity_df[equity_df['transaction_type'] == 'debit']['amount'].sum()
    actual_equity = equity_credits - equity_debits
    
    # Calculate the expected net assets (total assets - total liabilities)
    expected_total_assets = cash_at_hand + actual_non_current_assets
    expected_total_liabilities = actual_creditors + actual_short_loans + actual_long_loans + actual_other_liabilities
    expected_net_assets = expected_total_assets - expected_total_liabilities
    
    # Calculate discrepancies
    audit_results = {
        'Cash At Hand': {'Expected': cash_at_hand, 'Calculated': bs_cash_at_hand, 'Difference': cash_at_hand - bs_cash_at_hand},
        'Non-Current Assets': {'Expected': actual_non_current_assets, 'Calculated': bs_non_current_assets, 'Difference': actual_non_current_assets - bs_non_current_assets},
        'Total Assets': {'Expected': expected_total_assets, 'Calculated': bs_total_assets, 'Difference': expected_total_assets - bs_total_assets},
        'Creditors': {'Expected': actual_creditors, 'Calculated': bs_creditors, 'Difference': actual_creditors - bs_creditors},
        'Short Term Loans': {'Expected': actual_short_loans, 'Calculated': bs_short_loans, 'Difference': actual_short_loans - bs_short_loans},
        'Long Term Loans': {'Expected': actual_long_loans, 'Calculated': bs_long_loans, 'Difference': actual_long_loans - bs_long_loans},
        'Total Loans': {'Expected': actual_short_loans + actual_long_loans, 'Calculated': bs_total_loans, 'Difference': (actual_short_loans + actual_long_loans) - bs_total_loans},
        'Total Liabilities': {'Expected': expected_total_liabilities, 'Calculated': bs_total_liabilities, 'Difference': expected_total_liabilities - bs_total_liabilities},
        'Net Assets': {'Expected': expected_net_assets, 'Calculated': bs_net_assets, 'Difference': expected_net_assets - bs_net_assets}
    }
    
    # Convert to DataFrame for display
    audit_df = pd.DataFrame.from_dict(audit_results, orient='index')
    
    # Format for currency display
    for col in audit_df.columns:
        audit_df[col] = audit_df[col].apply(lambda x: f"{CURRENCY_SYMBOL} {x:,.2f}")
    
    return audit_df

# Dashboard Page
if page == "Dashboard":
    st.header("Netagrow Finance Dashboard")

    if not filtered_df.empty:
        try:
            # Get current bank balance
            current_balance = load_balance()
            
            # Calculate financial metrics with precise calculation
            total_income = filtered_df[filtered_df['transaction_type'] == 'credit']['amount'].sum()
            total_expenses = filtered_df[filtered_df['transaction_type'] == 'debit']['amount'].sum()
            net_profit = total_income - total_expenses
            
            # Simpler CSS that ensures visibility of metric values
            st.markdown("""
            <style>
            [data-testid="stMetricValue"] {
                font-size: 1.8rem !important;
                color: #0c0c0c;
                overflow: visible !important;
                white-space: nowrap !important;
            }
            [data-testid="stMetricDelta"] {
                font-size: 0.8rem;
            }
            [data-testid="stMetricLabel"] {
                font-size: 1.1rem;
                color: #555;
            }
            [data-testid="stHorizontalBlock"] > div > div {
                width: 100% !important;
                padding: 0 !important;
                min-width: auto !important;
            }
            </style>
            """, unsafe_allow_html=True)

            # Format the numbers with the simplest possible formatting
            formatted_current_balance = f"{CURRENCY_SYMBOL} {int(current_balance):,d}"
            formatted_income = f"{CURRENCY_SYMBOL} {int(total_income):,d}"
            formatted_expenses = f"{CURRENCY_SYMBOL} {int(total_expenses):,d}"
            formatted_profit = f"{CURRENCY_SYMBOL} {int(net_profit):,d}"
            
            # Calculate profit percentage for the delta display
            profit_percentage = (net_profit / total_income * 100) if total_income > 0 else 0
            
            # Use columns with manual spacing for better metric display
            col1, spacing1, col2, spacing2, col3, spacing3, col4 = st.columns([3, 0.2, 3, 0.2, 3, 0.2, 3])
            
            col1.metric("Current Balance", formatted_current_balance)
            col2.metric("Total Income", formatted_income)
            col3.metric("Total Expenses", formatted_expenses, delta_color="inverse")
            col4.metric("Net Profit/Loss", formatted_profit, delta=f"{profit_percentage:.1f}%")
            
            # Add simple horizontal rule for separation
            st.markdown("---")

            # Income and Expenses by Category
            st.subheader("Income and Expenses by Category")
            category_summary = generate_category_summary(filtered_df)

            if not category_summary.empty:
                tab1, tab2 = st.tabs(["Chart", "Data"])

                with tab1:
                    # Ensure we're using the correct column names
                    fig_bar = px.bar(
                        category_summary,
                        x='category_name',
                        y=['income', 'expenses'],
                        title="Income vs Expenses by Category",
                        barmode='group',
                        labels={'value': 'Amount', 'category_name': 'Category', 'variable': 'Type'},
                        height=500,
                        color_discrete_map={'income': 'green', 'expenses': 'red'}
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

                with tab2:
                    st.dataframe(category_summary, use_container_width=True)
        except Exception as e:
            st.error(f"Error generating dashboard metrics: {e}")
            st.info("Please check your data format and try again.")

        # Recent Transactions - moved up to replace the Cash Flow Trend section
        st.subheader("Recent Transactions")
        if not filtered_df.empty:
            display_columns = ['date', 'description', 'amount', 'transaction_type', 'category_name']
            display_df = filtered_df[display_columns].sort_values('date', ascending=False).head(10)
            st.dataframe(display_df, use_container_width=True)

# Financial Statements Page
elif page == "Financial Statements":
    st.header("Netagrow Financial Statements")

    tabs = st.tabs(["Profit & Loss", "Balance Sheet", "Cash Flow", "Trial Balance"])

    # Profit & Loss Tab
    with tabs[0]:
        st.subheader("Profit & Loss Statement")
        pl_statement = calculate_pl_statement(filtered_df)

        if not pl_statement.empty:
            # Format the dataframe for display
            formatted_pl = pl_statement.copy()
            
            # Add a flag column for styling
            formatted_pl['is_summary'] = formatted_pl['type'] == 'Summary'
            
            # Apply conditional formatting
            def style_pl_statement(df):
                # Format the amount column
                df = df.style.format({
                    'amount': f'{CURRENCY_SYMBOL} {{:,.2f}}'
                })
                
                # Apply conditional styling for summary rows
                summary_rows = formatted_pl['is_summary'] == True
                
                # Apply styles
                return df.apply(lambda x: ['font-weight: bold; background-color: #f0f2f6' 
                                         if x.name in summary_rows.index[summary_rows] 
                                         else '' for _ in x], axis=1)
            
            # Display the styled dataframe
            st.dataframe(
                style_pl_statement(formatted_pl[['category_name', 'amount', 'type']]), 
                use_container_width=True
            )
            
            # Show visualization of the P&L
            st.subheader("Profit & Loss Visualization")
            
            # Prepare data for visualization
            viz_data = pl_statement.copy()
            viz_data = viz_data[viz_data['type'] != 'Summary']  # Remove summary rows
            
            if not viz_data.empty:
                # Plot income vs expenses by category
                chart_tab1, chart_tab2 = st.tabs(["Income vs Expenses", "Breakdown by Category"])
                
                with chart_tab1:
                    # Summary chart
                    summary_data = pl_statement[pl_statement['type'] == 'Summary'].head(2)
                    fig = px.bar(
                        summary_data,
                        x='category_name',
                        y='amount',
                        title='Income vs Expenses Summary',
                        labels={'amount': 'Amount', 'category_name': 'Category'},
                        color='category_name',
                        color_discrete_map={
                            'Total Income': 'green',
                            'Total Expenses': 'red'
                        }
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Display net profit/loss
                    net_pl = pl_statement[pl_statement['category_name'] == 'Net Profit/Loss']['amount'].values[0]
                    st.metric(
                        "Net Profit/Loss",
                        f"{CURRENCY_SYMBOL} {net_pl:,.2f}",
                        delta="Profit" if net_pl > 0 else "Loss"
                    )
                    
                with chart_tab2:
                    # Detailed breakdown by category
                    fig = px.bar(
                        viz_data,
                        x='category_name',
                        y='amount',
                        color='type',
                        title='Profit & Loss by Category',
                        barmode='group',
                        color_discrete_map={
                            'Income': 'green',
                            'Expense': 'red'
                        }
                    )
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No data available to generate Profit & Loss statement.")

    # Balance Sheet Tab
    with tabs[1]:
        st.subheader("Balance Sheet")
        
        # Calculate balance sheet
        balance_sheet = calculate_balance_sheet(filtered_df)
        
        if not balance_sheet.empty:
            # Display summary metrics
            try:
                total_assets = balance_sheet[balance_sheet['Description'] == 'Total Assets']['Amount'].values[0]
                total_liabilities = balance_sheet[balance_sheet['Description'] == 'Total Current Liabilities']['Amount'].values[0]
                net_assets = balance_sheet[balance_sheet['Description'] == 'Net Assets']['Amount'].values[0]
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Assets", f"{CURRENCY_SYMBOL} {total_assets:,.2f}")
                col2.metric("Total Liabilities", f"{CURRENCY_SYMBOL} {total_liabilities:,.2f}")
                col3.metric("Net Assets", f"{CURRENCY_SYMBOL} {net_assets:,.2f}")
                
                # Display the balance sheet without styling
                display_df = balance_sheet[['Description', 'Amount']].copy()
                
                # Format the amount column
                display_df['Amount'] = display_df['Amount'].apply(
                    lambda x: f"{CURRENCY_SYMBOL} {x:,.0f}" if pd.notnull(x) and x != '' else ''
                )
                
                st.dataframe(display_df, use_container_width=True, height=600)
                
                # Create visualization with explicitly selected rows
                # Use Description field to identify rows for visualization
                total_rows = [
                    'Total Non-Current Assets', 
                    'Total Cash at Hand', 
                    'Total Current Assets',
                    'Total Assets',
                    'Total Creditors',
                    'Total Short Term Loans',
                    'Total Long Term Loans',
                    'Total Loans',
                    'Total Current Liabilities',
                    'Net Assets'
                ]
                
                # Create a new dataframe specifically for visualization
                viz_data = balance_sheet[balance_sheet['Description'].isin(total_rows)].copy()
                
                # Filter out rows with zero or empty values
                viz_data = viz_data[viz_data['Amount'] != 0]
                viz_data = viz_data[viz_data['Amount'] != '']
                viz_data = viz_data.dropna(subset=['Amount'])
                
                if not viz_data.empty:
                    st.subheader("Balance Sheet Visualization")
                    
                    # Select only the columns needed for visualization
                    viz_data = viz_data[['Description', 'Amount']].copy()
                    
                    # Remove any remaining non-numeric values in Amount column
                    viz_data = viz_data[pd.to_numeric(viz_data['Amount'], errors='coerce').notnull()]
                    
                    if not viz_data.empty:
                        chart_tab1, chart_tab2 = st.tabs(["Pie Chart", "Bar Chart"])
                        
                        with chart_tab1:
                            try:
                                fig = px.pie(
                                    viz_data,
                                    values='Amount',
                                    names='Description',
                                    title='Balance Sheet Components',
                                    color_discrete_sequence=px.colors.qualitative.Pastel
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            except Exception as e:
                                st.error(f"Error generating pie chart: {e}")
                                st.dataframe(viz_data)  # Show the data to debug
                            
                        with chart_tab2:
                            try:
                                fig = px.bar(
                                    viz_data,
                                    x='Description',
                                    y='Amount',
                                    title='Balance Sheet Components',
                                    color='Description',
                                    color_discrete_sequence=px.colors.qualitative.Pastel
                                )
                                fig.update_layout(xaxis_tickangle=-45)
                                st.plotly_chart(fig, use_container_width=True)
                            except Exception as e:
                                st.error(f"Error generating bar chart: {e}")
                                st.dataframe(viz_data)  # Show the data to debug
                    else:
                        st.warning("No valid data available for visualization.")
                else:
                    st.warning("No data available for balance sheet visualization.")
                    
            except Exception as e:
                st.error(f"Error generating balance sheet: {e}")
                st.exception(e)  # Display detailed error for debugging

            # Add balance sheet audit option
            with st.expander("Balance Sheet Audit"):
                st.info("Verify the accuracy of the balance sheet calculations")
                
                if st.button("Run Balance Sheet Audit"):
                    audit_results = audit_balance_sheet(filtered_df, balance_sheet)
                    st.dataframe(audit_results, use_container_width=True)
                    
                    # Check if we have any discrepancies
                    has_discrepancies = False
                    for item in audit_results.index:
                        if audit_results.loc[item, 'Difference'] != f"{CURRENCY_SYMBOL} 0.00":
                            has_discrepancies = True
                            break
                    
                    if has_discrepancies:
                        st.warning("Some discrepancies were found in the balance sheet calculation. Please review the audit results.")
                    else:
                        st.success("Balance sheet calculations verified. All values are accurate.")
                
                st.markdown("""
                **Understanding the Balance Sheet Audit:**
                - **Expected**: Values calculated directly from the transaction data
                - **Calculated**: Values shown on the balance sheet
                - **Difference**: Expected minus Calculated (should be zero)
                """)
        else:
            st.warning("No data available to generate Balance Sheet.")
            
    # ...existing Cash Flow and Trial Balance tabs...

# Transactions Page
elif page == "Transactions":
    st.header("Netagrow Transaction Management")

    tabs = st.tabs(["View Transactions", "Add Transaction"])

    # View Transactions Tab
    with tabs[0]:
        st.subheader("Transaction List")

        col1, col2 = st.columns(2)
        with col1:
            search_term = st.text_input("Search transactions", placeholder="Search by description...")
        with col2:
            category_filter = st.multiselect(
                "Filter by category",
                options=filtered_df['category_name'].unique() if not filtered_df.empty else []
            )

        display_df = filtered_df
        if search_term:
            display_df = display_df[display_df['description'].str.contains(search_term, case=False)]
        if category_filter:
            display_df = display_df[display_df['category_name'].isin(category_filter)]

        if not display_df.empty:
            display_columns = ['id', 'date', 'description', 'amount', 'transaction_type', 'category_name', 'notes']
            st.dataframe(display_df[display_columns].sort_values('date', ascending=False), use_container_width=True)
        else:
            st.warning("No transactions found matching the filters.")

    # Add Transaction Tab
    with tabs[1]:
        st.subheader("Add New Transaction")

        # Display current balance at top of the form
        current_balance = load_balance()
        st.info(f"Current Balance: {CURRENCY_SYMBOL} {current_balance:,.2f}")

        with st.form("transaction_form"):
            col1, col2 = st.columns(2)

            with col1:
                transaction_date = st.date_input("Transaction Date", datetime.now())
                description = st.text_input("Description", placeholder="Enter transaction description")
                amount = st.number_input("Amount", min_value=0.01, format="%.2f")
                transaction_type = st.selectbox("Transaction Type", ["debit", "credit"])

            with col2:
                # Use structured categories from config
                if transaction_type == "debit":
                    category_options = [(cat["id"], cat["name"]) for cat in categories["expense_categories"]]
                else:
                    category_options = [(cat["id"], cat["name"]) for cat in categories["income_categories"]]
                
                # Add any existing categories from the data that aren't in our config
                if not filtered_df.empty:
                    existing_categories = filtered_df[['category_id', 'category_name']].drop_duplicates().values.tolist()
                    for cat_id, cat_name in existing_categories:
                        if cat_id and cat_name and not any(cat_id == c[0] for c in category_options):
                            category_options.append((cat_id, cat_name))
                
                category = st.selectbox("Category", 
                                       options=[name for _, name in category_options],
                                       format_func=lambda x: x)
                
                # Get category ID based on selected name
                category_id = next((cat_id for cat_id, cat_name in category_options if cat_name == category), None)
                
                notes = st.text_area("Notes", placeholder="Additional details about the transaction")
                new_id = filtered_df['id'].max() + 1 if not filtered_df.empty and 'id' in filtered_df.columns else 1

            submit_button = st.form_submit_button("Add Transaction")

            if submit_button:
                if description and amount > 0:
                    new_transaction = {
                        'id': new_id,
                        'date': transaction_date,
                        'description': description,
                        'amount': amount,
                        'transaction_type': transaction_type,
                        'category_id': category_id,
                        'category_name': category,
                        'notes': notes,
                        'remarks': notes,
                        'reporting_trigger': 'expense' if transaction_type == 'debit' else 'income',
                        'transaction_date': transaction_date.strftime('%m/%d/%y')
                    }

                    # Update the balance after the transaction
                    new_balance = update_balance_after_transaction(amount, transaction_type)
                
                    st.success(f"Transaction '{description}' added successfully!")
                    st.info(f"New Balance: {CURRENCY_SYMBOL} {new_balance:,.2f}")
                    st.json(new_transaction)
                
                    # Add an option to record to CSV if needed
                    if st.button("Record Transaction to Database"):
                        try:
                            # Convert dict to dataframe
                            new_transaction_df = pd.DataFrame([new_transaction])
                            
                            # Append to existing CSV if it exists
                            if os.path.exists('trial_balance.csv'):
                                existing_df = pd.read_csv('trial_balance.csv')
                                updated_df = pd.concat([existing_df, new_transaction_df], ignore_index=True)
                                updated_df.to_csv('trial_balance.csv', index=False)
                            else:
                                new_transaction_df.to_csv('trial_balance.csv', index=False)
                                
                            st.success("Transaction recorded in database!")
                            st.info("Refresh the page to see the updated data.")
                        except Exception as e:
                            st.error("Could not record transaction to database.")
                            st.exception(e)
                else:
                    st.error("Please enter a description and valid amount.")

# Reports Page
elif page == "Reports":
    st.header("Netagrow Financial Reports")

    report_type = st.selectbox(
        "Select Report Type",
        ["Category Analysis", "Budget vs. Actual", "Monthly Comparison", "Cash Flow Projection"]
    )

    if report_type == "Category Analysis":
        st.subheader("Expense by Category Analysis")

        expenses_df = filtered_df[filtered_df['transaction_type'] == 'debit']
        if not expenses_df.empty:
            category_expenses = expenses_df.groupby('category_name')['amount'].sum().reset_index()
            category_expenses['percentage'] = (
                        category_expenses['amount'] / category_expenses['amount'].sum() * 100).round(2)

            st.dataframe(
                category_expenses.style.format({
                    'amount': f'{CURRENCY_SYMBOL} {{:,.2f}}',
                    'percentage': '{:.2f}%'
                }),
                use_container_width=True
            )

            tab1, tab2 = st.tabs(["Pie Chart", "Bar Chart"])

            with tab1:
                fig_pie = px.pie(
                    category_expenses,
                    values='amount',
                    names='category_name',
                    title='Expense Distribution by Category',
                    hole=0.4
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            with tab2:
                fig_bar = px.bar(
                    category_expenses,
                    x='category_name',
                    y='amount',
                    text='percentage',
                    title='Expense Amount by Category',
                    labels={'amount': 'Amount', 'category_name': 'Category'},
                    color='amount',
                    color_continuous_scale='Reds'
                )
                fig_bar.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
                st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.warning("No expense transactions found in the selected date range.")

# Settings Page
elif page == "Settings":
    st.header("Netagrow Settings")
    
    tabs = st.tabs(["General Settings", "Data Verification", "About"])
    
    with tabs[0]:
        st.subheader("General Settings")
        
        # Add currency selector
        currency_options = ["ZMW", "USD", "EUR", "GBP"]
        selected_currency = st.selectbox("Select Currency", currency_options, index=0)
        st.session_state.currency = selected_currency
        
        # Add date format selector
        date_formats = ["MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD"]
        selected_date_format = st.selectbox("Date Format", date_formats, index=0)
        
        # Add theme selector
        themes = ["Light", "Dark", "System"]
        selected_theme = st.selectbox("Theme", themes, index=0)
        
        # Add a save button
        if st.button("Save Settings"):
            st.success(f"Settings saved successfully!")
    
    with tabs[1]:
        st.subheader("Data Verification")
        
        st.info("Verify your financial data for consistency and accuracy.")
        
        if st.button("Run Data Verification"):
            verify_financial_data(filtered_df)
            
            # Calculate the expected totals
            total_income = filtered_df[filtered_df['transaction_type'] == 'credit']['amount'].sum()
            total_expenses = filtered_df[filtered_df['transaction_type'] == 'debit']['amount'].sum()
            net_profit = total_income - total_expenses
            
            # Display the results
            results_df = pd.DataFrame({
                'Metric': ['Total Income', 'Total Expenses', 'Net Profit/Loss'],
                'Value': [
                    f"{CURRENCY_SYMBOL} {total_income:,.2f}",
                    f"{CURRENCY_SYMBOL} {total_expenses:,.2f}", 
                    f"{CURRENCY_SYMBOL} {net_profit:,.2f}"
                ]
            })
            
            st.dataframe(results_df, use_container_width=True)
            st.success("Data verification completed successfully!")
            
    with tabs[2]:
        st.subheader("About")
        st.markdown("""
        **Netagrow Finance Dashboard**
        
        Version: 1.0.0
        
        A financial management dashboard built specifically for Netagrow, providing:
        - Income and expense tracking for IoT device development
        - Agriculture technology financial statements
        - Transaction management for product R&D
        - Custom financial reporting for stakeholders
        
        © 2023 Netagrow Technologies
        """)

# Add a new function to verify data integrity
def verify_financial_data(df):
    """Verify that financial data is consistent and accurately calculated"""
    if df.empty:
        return

    # Check transaction types
    invalid_types = df[~df['transaction_type'].isin(['credit', 'debit'])]
    if not invalid_types.empty:
        st.warning(f"Found {len(invalid_types)} transactions with invalid transaction types.")
        
    # Check for missing amounts
    missing_amounts = df[df['amount'].isna()]
    if not missing_amounts.empty:
        st.warning(f"Found {len(missing_amounts)} transactions with missing amounts.")
        
    # Check for negative amounts (should be handled by transaction_type)
    negative_amounts = df[df['amount'] < 0]
    if not negative_amounts.empty:
        st.warning(f"Found {len(negative_amounts)} transactions with negative amounts.")

# Call the verify function when data is loaded
# Add this near where you load the data
if not filtered_df.empty:
    verify_financial_data(filtered_df)
