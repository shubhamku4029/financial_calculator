import dash
from dash import dcc, html, Input, Output
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# ==============================================================================
# 1. YOUR BACKEND LOGIC (Fixed syntax and parameter alignment)
# ==============================================================================

DEFAULT_ASSUMPTIONS = {
    "epf_interest_rate": 0.0825,     
    "epf_employee_pct": 0.12,         
    "epf_employer_pct": 0.12,    
    "nps_expected_return": 0.10,      
    "salary_growth_rate": 0.07,      
    "inflation_rate": 0.06,          
    "wecare_discount_rate": 0.07,     
    "wecare_commutation_pct": 0.33,  
    "standard_deduction": 75000,      
}

def estimate_annual_tax(taxable_income, assumptions=DEFAULT_ASSUMPTIONS):
    income = max(0, taxable_income - assumptions["standard_deduction"])
    slabs = [
        (400_000, 0.00),
        (800_000, 0.05),
        (1_200_000, 0.10),
        (1_600_000, 0.15),
        (2_000_000, 0.20),
        (2_400_000, 0.25),
        (float("inf"), 0.30),
    ]
    tax = 0.0
    lower = 0
    for upper, rate in slabs:
        if income <= lower:
            break
        taxable_in_slab = min(income, upper) - lower
        tax += taxable_in_slab * rate
        lower = upper
    tax *= 1.04 
    return round(tax, 2)

def project_epf_balance(opening_balance, annual_basic_salary, assumptions=DEFAULT_ASSUMPTIONS):
    contribution = annual_basic_salary * (assumptions["epf_employee_pct"] + assumptions["epf_employer_pct"])
    interest = (opening_balance + contribution / 2) * assumptions["epf_interest_rate"]
    closing_balance = opening_balance + contribution + interest
    return closing_balance, contribution, interest

def project_nps_balance(opening_balance, annual_salary, employee_pct, employer_pct, assumptions=DEFAULT_ASSUMPTIONS):
    contribution = annual_salary * (employee_pct + employer_pct)
    growth = (opening_balance + contribution / 2) * assumptions["nps_expected_return"]
    closing_balance = opening_balance + contribution + growth
    return closing_balance, contribution, growth

def calculate_wecare_benefit(final_avg_annual_salary, retirement_age=60, life_expectancy=80, assumptions=DEFAULT_ASSUMPTIONS):
    guaranteed_monthly_pension = 0.50 * final_avg_annual_salary / 12
    annuity_years = life_expectancy - retirement_age
    monthly_rate = assumptions["wecare_discount_rate"] / 12
    n_months = annuity_years * 12

    if monthly_rate > 0:
        annuity_factor = (1 - (1 + monthly_rate) ** (-n_months)) / monthly_rate
    else:
        annuity_factor = n_months

    full_lump_sum_equivalent = guaranteed_monthly_pension * annuity_factor
    commutable_lump_sum = full_lump_sum_equivalent * assumptions["wecare_commutation_pct"]
    residual_monthly_pension = guaranteed_monthly_pension * (1 - assumptions["wecare_commutation_pct"])

    return {
        "guaranteed_monthly_pension": round(guaranteed_monthly_pension, 2),
        "full_lump_sum_equivalent": round(full_lump_sum_equivalent, 2),
        "commutable_lump_sum": round(commutable_lump_sum, 2),
        "residual_monthly_pension": round(residual_monthly_pension, 2),
    }

def calculate_take_home(annual_gross_salary, nps_employee_pct, wecare_enabled, assumptions=DEFAULT_ASSUMPTIONS):
    epf_deduction = annual_gross_salary * assumptions["epf_employee_pct"]
    nps_deduction = annual_gross_salary * nps_employee_pct
    wecare_deduction = annual_gross_salary * 0.10 if wecare_enabled else 0.0

    taxable_income = annual_gross_salary - epf_deduction - nps_deduction
    tax = estimate_annual_tax(taxable_income, assumptions)

    net_annual = annual_gross_salary - epf_deduction - nps_deduction - wecare_deduction - tax

    return {
        "gross_annual": round(annual_gross_salary, 2),
        "epf_deduction": round(epf_deduction, 2),
        "nps_deduction": round(nps_deduction, 2),
        "wecare_deduction": round(wecare_deduction, 2),
        "estimated_tax": tax,
        "net_annual": round(net_annual, 2),
        "net_monthly": round(net_annual / 12, 2),
    }

def calculate_replacement_ratio(corpus, final_annual_salary, retirement_age=60, life_expectancy=80, assumptions=DEFAULT_ASSUMPTIONS):
    annuity_years = life_expectancy - retirement_age
    monthly_rate = assumptions["wecare_discount_rate"] / 12
    n_months = annuity_years * 12

    if monthly_rate > 0:
        annuity_factor = (1 - (1 + monthly_rate) ** (-n_months)) / monthly_rate
    else:
        annuity_factor = n_months

    monthly_pension_from_corpus = corpus / annuity_factor
    final_monthly_salary = final_annual_salary / 12
    replacement_ratio_pct = (monthly_pension_from_corpus / final_monthly_salary) * 100
    return round(replacement_ratio_pct, 2)

def project_retirement(current_age, retirement_age, starting_salary, nps_employee_pct=0.0, nps_employer_pct=0.0, wecare_enabled=True, assumptions=DEFAULT_ASSUMPTIONS):
    years = retirement_age - current_age
    rows = []
    salary = starting_salary
    epf_balance = 0.0
    nps_balance = 0.0

    for year in range(years):
        age = current_age + year
        epf_balance, epf_contribution, epf_interest = project_epf_balance(epf_balance, salary, assumptions)
        nps_balance, nps_contribution, nps_growth = project_nps_balance(nps_balance, salary, nps_employee_pct, nps_employer_pct, assumptions)
        take_home = calculate_take_home(salary, nps_employee_pct, wecare_enabled, assumptions)

        rows.append({
            "age": age,
            "year_number": year + 1,
            "gross_salary": round(salary, 2),
            "epf_contribution": round(epf_contribution, 2),
            "epf_balance": round(epf_balance, 2),
            "nps_contribution": round(nps_contribution, 2),
            "nps_balance": round(nps_balance, 2),
            "total_corpus": round(epf_balance + nps_balance, 2),
            "net_take_home_annual": take_home["net_annual"],
            "net_take_home_monthly": take_home["net_monthly"],
        })

        salary *= (1 + assumptions["salary_growth_rate"]) 

    df = pd.DataFrame(rows)
    final_avg_salary = df.iloc[-1]["gross_salary"] if not df.empty else starting_salary
    wecare_benefit = calculate_wecare_benefit(final_avg_salary, retirement_age, 80, assumptions) if wecare_enabled else None

    return df, wecare_benefit

# ==============================================================================
# 2. PLOTLY DASH FRONT-END DESIGN
# ==============================================================================

app = dash.Dash(__name__)

# --- Design Tokens ---
COLORS = {
    'primary': '#550000',      # Your brand red
    'secondary': '#8B0000',    # Lighter red for gradients/charts
    'background': '#F4F6F9',   # Off-white dashboard background
    'surface': '#FFFFFF',      # Card background
    'text_dark': '#1E293B',
    'text_light': '#64748B',
    'border': '#E2E8F0'
}

# --- Shared Styles ---
card_style = {
    'backgroundColor': COLORS['surface'], 'padding': '24px', 
    'borderRadius': '12px', 'boxShadow': '0 4px 6px -1px rgba(0, 0, 0, 0.05)',
    'border': f"1px solid {COLORS['border']}"
}
kpi_label_style = {'fontSize': '14px', 'color': COLORS['text_light'], 'margin': '0 0 8px 0', 'fontWeight': '600', 'textTransform': 'uppercase'}
kpi_value_style = {'fontSize': '28px', 'color': COLORS['primary'], 'margin': '0', 'fontWeight': '700'}
input_style = {'width': '100%', 'padding': '10px', 'borderRadius': '6px', 'border': f"1px solid {COLORS['border']}", 'marginBottom': '20px', 'boxSizing': 'border-box'}

# --- App Layout ---
app.layout = html.Div(style={'backgroundColor': COLORS['background'], 'minHeight': '100vh', 'fontFamily': '"Segoe UI", system-ui, sans-serif', 'padding': '40px'}, children=[
    
    # Header
    html.Div(style={'marginBottom': '30px'}, children=[
        html.H1("Executive Retirement Projections", style={'color': COLORS['text_dark'], 'margin': '0 0 8px 0'}),
        html.P("Comprehensive EPF, NPS, and WeCare financial modeling.", style={'color': COLORS['text_light'], 'margin': '0'})
    ]),

    # Main Grid (Sidebar + Main Content)
    html.Div(style={'display': 'flex', 'gap': '30px', 'flexWrap': 'wrap'}, children=[
        
        # --- LEFT SIDEBAR: INPUTS ---
        html.Div(style={**card_style, 'flex': '1', 'minWidth': '300px', 'maxWidth': '350px'}, children=[
            html.H3("Assumptions & Inputs", style={'color': COLORS['primary'], 'marginTop': '0', 'marginBottom': '24px'}),
            
            html.Label("Current Age", style={'fontWeight': 'bold', 'color': COLORS['text_dark']}),
            dcc.Input(id='in-age', type='number', value=28, style=input_style),
            
            html.Label("Retirement Age", style={'fontWeight': 'bold', 'color': COLORS['text_dark']}),
            dcc.Input(id='in-ret-age', type='number', value=60, style=input_style),
            
            html.Label("Current Annual Salary (₹)", style={'fontWeight': 'bold', 'color': COLORS['text_dark']}),
            dcc.Input(id='in-salary', type='number', value=2000000, style=input_style),
            
            html.Label("NPS Employee Contribution (%)", style={'fontWeight': 'bold', 'color': COLORS['text_dark']}),
            dcc.Slider(id='in-nps-emp', min=0, max=10, step=1, value=5, marks={i: f"{i}%" for i in range(0, 11, 2)}),
            html.Br(),
            
            html.Label("NPS Employer Contribution (%)", style={'fontWeight': 'bold', 'color': COLORS['text_dark']}),
            dcc.Slider(id='in-nps-empr', min=0, max=10, step=1, value=5, marks={i: f"{i}%" for i in range(0, 11, 2)}),
            html.Br(),
            
            html.Label("Enable WeCare Benefit", style={'fontWeight': 'bold', 'color': COLORS['text_dark']}),
            dcc.RadioItems(
                id='in-wecare',
                options=[{'label': ' Yes', 'value': True}, {'label': ' No', 'value': False}],
                value=True,
                style={'marginTop': '10px'}
            )
        ]),

        # --- RIGHT AREA: OUTPUTS & CHARTS ---
        html.Div(style={'flex': '3', 'minWidth': '600px', 'display': 'flex', 'flexDirection': 'column', 'gap': '30px'}, children=[
            
            # Top KPI Cards
            html.Div(style={'display': 'grid', 'gridTemplateColumns': 'repeat(auto-fit, minmax(200px, 1fr))', 'gap': '20px'}, children=[
                html.Div(style={**card_style, 'borderTop': f"4px solid {COLORS['primary']}"}, children=[
                    html.P("Total Corpus at Retirement", style=kpi_label_style),
                    html.H2(id='kpi-corpus', style=kpi_value_style)
                ]),
                html.Div(style={**card_style, 'borderTop': f"4px solid {COLORS['primary']}"}, children=[
                    html.P("Replacement Ratio", style=kpi_label_style),
                    html.H2(id='kpi-ratio', style=kpi_value_style)
                ]),
                html.Div(style={**card_style, 'borderTop': f"4px solid {COLORS['primary']}"}, children=[
                    html.P("Final Net Monthly Income", style=kpi_label_style),
                    html.H2(id='kpi-takehome', style={'fontSize': '24px', 'color': COLORS['text_dark'], 'margin': '0', 'fontWeight': '700'})
                ]),
                html.Div(id='kpi-wecare-card', style={**card_style, 'borderTop': f"4px solid {COLORS['primary']}"}, children=[
                    html.P("WeCare Monthly Pension", style=kpi_label_style),
                    html.H2(id='kpi-wecare', style={'fontSize': '24px', 'color': COLORS['text_dark'], 'margin': '0', 'fontWeight': '700'})
                ]),
            ]),

            # Charts
            html.Div(style=card_style, children=[
                dcc.Graph(id='chart-corpus')
            ]),
            html.Div(style=card_style, children=[
                dcc.Graph(id='chart-salary')
            ])
        ])
    ])
])

# ==============================================================================
# 3. INTERACTIVITY: Connect Inputs to Backend
# ==============================================================================

@app.callback(
    [Output('kpi-corpus', 'children'),
     Output('kpi-ratio', 'children'),
     Output('kpi-takehome', 'children'),
     Output('kpi-wecare', 'children'),
     Output('kpi-wecare-card', 'style'), # Hide if WeCare is disabled
     Output('chart-corpus', 'figure'),
     Output('chart-salary', 'figure')],
    [Input('in-age', 'value'),
     Input('in-ret-age', 'value'),
     Input('in-salary', 'value'),
     Input('in-nps-emp', 'value'),
     Input('in-nps-empr', 'value'),
     Input('in-wecare', 'value')]
)
def update_dashboard(age, ret_age, salary, nps_emp, nps_empr, wecare):
    # Prevent calculation if inputs are cleared
    if None in [age, ret_age, salary, nps_emp, nps_empr]:
        return dash.no_update

    # Convert UI percentages (5) to math percentages (0.05)
    nps_emp_pct = nps_emp / 100
    nps_empr_pct = nps_empr / 100

    # 1. RUN YOUR BACKEND CALCULATION
    df, wecare_data = project_retirement(
        current_age=age, 
        retirement_age=ret_age, 
        starting_salary=salary,
        nps_employee_pct=nps_emp_pct, 
        nps_employer_pct=nps_empr_pct, 
        wecare_enabled=wecare
    )

    if df.empty:
        return "N/A", "N/A", "N/A", "N/A", {'display': 'none'}, go.Figure(), go.Figure()

    # 2. EXTRACT KPIs
    final_row = df.iloc[-1]
    total_corpus = final_row['total_corpus']
    final_salary = final_row['gross_salary']
    
    ratio = calculate_replacement_ratio(total_corpus, final_salary, retirement_age=ret_age)
    
    # Format strings
    str_corpus = f"₹{total_corpus:,.0f}"
    str_ratio = f"{ratio}%"
    str_takehome = f"₹{final_row['net_take_home_monthly']:,.0f} / mo"
    
    if wecare and wecare_data:
        str_wecare = f"₹{wecare_data['guaranteed_monthly_pension']:,.0f} / mo"
        wecare_style = {**card_style, 'borderTop': f"4px solid {COLORS['primary']}", 'display': 'block'}
    else:
        str_wecare = ""
        wecare_style = {'display': 'none'} # Hide the card entirely

    # 3. BUILD CHARTS
    # Chart 1: Stacked Area of Corpus Growth
    fig_corpus = go.Figure()
    fig_corpus.add_trace(go.Scatter(x=df['age'], y=df['epf_balance'], mode='lines', line=dict(width=0.5, color=COLORS['primary']), fill='tozeroy', name='EPF Balance'))
    fig_corpus.add_trace(go.Scatter(x=df['age'], y=df['nps_balance'], mode='lines', line=dict(width=0.5, color='#A52A2A'), fill='tonexty', name='NPS Balance'))
    fig_corpus.update_layout(
        title='Wealth Accumulation Over Time',
        xaxis_title='Age',
        yaxis_title='Corpus (₹)',
        template='plotly_white',
        hovermode='x unified',
        margin=dict(l=20, r=20, t=50, b=20)
    )

    # Chart 2: Salary vs Take Home
    fig_salary = go.Figure()
    fig_salary.add_trace(go.Scatter(x=df['age'], y=df['gross_salary'], mode='lines', name='Gross Annual Salary', line=dict(color=COLORS['text_light'], dash='dash')))
    fig_salary.add_trace(go.Scatter(x=df['age'], y=df['net_take_home_annual'], mode='lines', name='Net Take-Home', line=dict(color=COLORS['primary'], width=3)))
    fig_salary.update_layout(
        title='Income Projection (Gross vs Net)',
        xaxis_title='Age',
        yaxis_title='Annual Amount (₹)',
        template='plotly_white',
        hovermode='x unified',
        margin=dict(l=20, r=20, t=50, b=20)
    )

    return str_corpus, str_ratio, str_takehome, str_wecare, wecare_style, fig_corpus, fig_salary

if __name__ == '__main__':
    app.run(debug=True)