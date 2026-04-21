import streamlit as st
import yfinance as yf
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

# Page configuration TEste  2
st.set_page_config(
    page_title="Market Regime Analysis - ITUB4.SA",
    page_icon="📈",
    layout="wide"
)

# Title and description
st.title("📊 Market Regime Analysis with K-Means Clustering")
st.markdown("""
This application analyzes **ITUB4.SA** stock using K-Means clustering on moving average features 
to identify different market regimes (Bull, Neutral, Bear).
""")

# Sidebar for parameters
st.sidebar.header("⚙️ Parameters")

# Date range selection
end_date = pd.Timestamp.today().strftime('%Y-%m-%d')
start_date_train = st.sidebar.date_input(
    "Training Start Date",
    value=pd.to_datetime("2015-01-01"),
    max_value=pd.to_datetime("2022-12-31")
)

end_date_train = st.sidebar.date_input(
    "Training End Date",
    value=pd.to_datetime("2022-12-31"),
    max_value=pd.to_datetime(end_date)
)

start_date_test = st.sidebar.date_input(
    "Test Start Date",
    value=pd.to_datetime("2023-01-01"),
    max_value=pd.to_datetime(end_date)
)

# Number of clusters
n_clusters = st.sidebar.slider(
    "Number of Regimes (Clusters)",
    min_value=2,
    max_value=5,
    value=3,
    help="Number of market regimes to identify"
)

# Rolling window for smoothing
smoothing_window = st.sidebar.slider(
    "Regime Smoothing Window (days)",
    min_value=1,
    max_value=21,
    value=5,
    help="Moving window to smooth regime changes"
)

# MA windows range
ma_min = st.sidebar.slider("Minimum MA Window", min_value=3, max_value=10, value=5)
ma_max = st.sidebar.slider("Maximum MA Window", min_value=11, max_value=50, value=21)

# Run analysis button
run_analysis = st.sidebar.button("🚀 Run Analysis", type="primary")

# Cache data loading
@st.cache_data(ttl=3600)
def load_data(ticker="ITUB4.SA", start="2015-01-01", end=None):
    """Load stock data from Yahoo Finance"""
    if end is None:
        end = pd.Timestamp.today().strftime('%Y-%m-%d')
    
    df = yf.download(
        ticker,
        start=start,
        end=end,
        auto_adjust=False,
        progress=False
    )
    
    # Handle multi-level columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    
    return df

@st.cache_data
def prepare_features(df, ma_min=5, ma_max=21):
    """Prepare features for clustering"""
    df['ret_1d'] = df['Close'].pct_change()
    
    # Create moving averages
    for window in range(ma_min, ma_max + 1):
        df[f'ret_ma{window}'] = df['ret_1d'].rolling(window).mean()
    
    df = df.dropna()
    return df

def run_clustering_analysis(df_train, df_test, feature_cols, n_clusters=3, smoothing_window=5):
    """Run the complete clustering analysis"""
    
    # Standardization
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(df_train[feature_cols])
    X_test_scaled = scaler.transform(df_test[feature_cols])
    
    # Train K-Means
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    kmeans.fit(X_train_scaled)
    
    # Get centers in original scale
    centers_original = scaler.inverse_transform(kmeans.cluster_centers_)
    
    # Order clusters by momentum
    cluster_means = centers_original.mean(axis=1)
    sorted_indices = np.argsort(cluster_means)
    regime_mapping = {sorted_indices[i]: i for i in range(n_clusters)}
    
    # Predict regimes
    df_test['regime_original'] = kmeans.predict(X_test_scaled)
    df_test['regime'] = df_test['regime_original'].map(regime_mapping)
    
    # Smooth regimes (no look-ahead bias)
    df_test['regime_suave'] = (
        df_test['regime']
        .rolling(smoothing_window, min_periods=1)
        .apply(lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[-1])
    )
    
    # Run without standardization for comparison
    kmeans_no_scale = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    kmeans_no_scale.fit(df_train[feature_cols])
    
    centers_no_scale = kmeans_no_scale.cluster_centers_
    means_no_scale = centers_no_scale.mean(axis=1)
    sorted_no_scale = np.argsort(means_no_scale)
    mapping_no_scale = {sorted_no_scale[i]: i for i in range(n_clusters)}
    
    df_test['regime_sem_pad'] = kmeans_no_scale.predict(df_test[feature_cols])
    df_test['regime_sem_pad'] = df_test['regime_sem_pad'].map(mapping_no_scale)
    
    return df_test, scaler, kmeans, centers_original, regime_mapping

# Main execution
if run_analysis:
    with st.spinner("Loading data and running analysis..."):
        # Load data
        df_full = load_data(
            "ITUB4.SA",
            start=start_date_train.strftime('%Y-%m-%d'),
            end=end_date
        )
        
        # Prepare features
        df_full = prepare_features(df_full, ma_min, ma_max)
        
        # Split data
        df_train = df_full[
            (df_full.index >= pd.Timestamp(start_date_train)) & 
            (df_full.index <= pd.Timestamp(end_date_train))
        ].copy()
        
        df_test = df_full[
            (df_full.index >= pd.Timestamp(start_date_test)) & 
            (df_full.index <= pd.Timestamp(end_date))
        ].copy()
        
        # Feature columns
        feature_cols = [f'ret_ma{window}' for window in range(ma_min, ma_max + 1)]
        
        # Run clustering
        df_test, scaler, kmeans, centers_original, regime_mapping = run_clustering_analysis(
            df_train, df_test, feature_cols, n_clusters, smoothing_window
        )
        
        # Display results
        st.success("✅ Analysis completed successfully!")
        
        # Create tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs([
            "📈 Price Chart", 
            "📊 Regime Analysis", 
            "🔬 Technical Details",
            "⚠️ Scale Sensitivity"
        ])
        
        with tab1:
            st.subheader("ITUB4.SA Price with Market Regimes")
            
            # Color mapping
            colors = {0: 'red', 1: 'yellow', 2: 'green'}
            if n_clusters > 3:
                # Add more colors if needed
                extra_colors = ['orange', 'purple', 'cyan', 'magenta']
                for i in range(3, n_clusters):
                    colors[i] = extra_colors[i-3]
            
            regime_names = {
                0: 'Low Momentum (Bear)',
                1: 'Medium Momentum (Neutral)',
                2: 'High Momentum (Bull)'
            }
            
            # Create plot
            fig = go.Figure()
            
            # Colored line segments
            for i in range(len(df_test) - 1):
                regime_atual = int(df_test['regime_suave'].iloc[i])
                cor = colors.get(regime_atual, 'gray')
                
                fig.add_trace(go.Scatter(
                    x=[df_test.index[i], df_test.index[i+1]],
                    y=[df_test['Close'].iloc[i], df_test['Close'].iloc[i+1]],
                    mode='lines',
                    line=dict(color=cor, width=2),
                    showlegend=False,
                    hoverinfo='none'
                ))
            
            # Markers
            fig.add_trace(go.Scatter(
                x=df_test.index,
                y=df_test['Close'],
                mode='markers',
                marker=dict(
                    size=3,
                    color=[colors.get(int(r), 'gray') for r in df_test['regime_suave']],
                    showscale=False
                ),
                text=[f"Date: {d.strftime('%Y-%m-%d')}<br>Price: R${p:.2f}<br>"
                      f"Regime: {regime_names.get(int(r), 'Unknown')}<br>"
                      f"MA5: {ma5:.4%}<br>MA10: {ma10:.4%}<br>MA21: {ma21:.4%}" 
                      for d, p, r, ma5, ma10, ma21 in zip(
                          df_test.index, df_test['Close'], df_test['regime_suave'],
                          df_test['ret_ma5'], df_test['ret_ma10'], df_test['ret_ma21']
                      )],
                hoverinfo='text',
                showlegend=False
            ))
            
            # Legend
            for regime in range(n_clusters):
                regime_name = f"Regime {regime}"
                if regime in regime_names:
                    regime_name = regime_names[regime]
                fig.add_trace(go.Scatter(
                    x=[None],
                    y=[None],
                    mode='lines',
                    line=dict(color=colors.get(regime, 'gray'), width=3),
                    name=regime_name,
                    showlegend=True
                ))
            
            fig.update_layout(
                title=f"ITUB4.SA - Market Regimes (K-Means with {n_clusters} clusters)",
                xaxis_title="Date",
                yaxis_title="Price (R$)",
                template="plotly_dark",
                hovermode='x unified',
                legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
                height=600
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Regime distribution pie chart
            st.subheader("Regime Distribution")
            regime_counts = df_test['regime_suave'].value_counts().sort_index()
            
            col1, col2 = st.columns(2)
            with col1:
                fig_pie = go.Figure(data=[go.Pie(
                    labels=[f"Regime {i}" for i in regime_counts.index],
                    values=regime_counts.values,
                    marker_colors=[colors.get(i, 'gray') for i in regime_counts.index],
                    hole=.3
                )])
                fig_pie.update_layout(title="Regime Distribution in Test Period")
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                st.dataframe(
                    pd.DataFrame({
                        'Regime': regime_counts.index,
                        'Days': regime_counts.values,
                        'Percentage': f"{regime_counts.values/len(df_test)*100:.1f}%"
                    }),
                    use_container_width=True
                )
        
        with tab2:
            st.subheader("Regime Performance Analysis")
            
            # Performance metrics by regime
            regime_metrics = []
            for regime in range(n_clusters):
                df_reg = df_test[df_test['regime_suave'] == regime]
                if len(df_reg) > 0:
                    regime_metrics.append({
                        'Regime': regime,
                        'Days': len(df_reg),
                        'Percentage': f"{len(df_reg)/len(df_test)*100:.1f}%",
                        'Avg Price': f"R${df_reg['Close'].mean():.2f}",
                        'Avg Daily Return': f"{df_reg['ret_1d'].mean()*100:.4f}%",
                        'Volatility': f"{df_reg['ret_1d'].std()*100:.4f}%",
                        'Sharpe (approx)': f"{df_reg['ret_1d'].mean()/df_reg['ret_1d'].std()*np.sqrt(252):.2f}"
                    })
            
            if regime_metrics:
                st.dataframe(pd.DataFrame(regime_metrics), use_container_width=True)
            
            # Moving average profiles
            st.subheader("Moving Average Profiles by Regime")
            
            ma_profile_data = []
            for regime in range(n_clusters):
                df_reg = df_test[df_test['regime_suave'] == regime]
                if len(df_reg) > 0:
                    row = {'Regime': regime}
                    for window in [5, 10, 15, 21] + [ma_max] if ma_max not in [5,10,15,21] else []:
                        if window <= ma_max:
                            row[f'MA{window}'] = f"{df_reg[f'ret_ma{window}'].mean()*100:.4f}%"
                    ma_profile_data.append(row)
            
            if ma_profile_data:
                st.dataframe(pd.DataFrame(ma_profile_data), use_container_width=True)
            
            # Transition matrix
            st.subheader("Regime Transition Matrix")
            transitions = pd.crosstab(
                df_test['regime_suave'].shift(),
                df_test['regime_suave'],
                normalize='index'
            ) * 100
            
            st.dataframe(transitions.round(2), use_container_width=True)
            st.caption("Shows probability (%) of transitioning from one regime to another")
        
        with tab3:
            st.subheader("Technical Details")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Model Configuration")
                st.markdown(f"""
                - **Ticker:** ITUB4.SA
                - **Training Period:** {start_date_train} to {end_date_train}
                - **Test Period:** {start_date_test} to {end_date}
                - **Number of Clusters:** {n_clusters}
                - **Smoothing Window:** {smoothing_window} days
                - **MA Features:** {ma_min} to {ma_max} days ({len(feature_cols)} features)
                - **Random Seed:** 42
                """)
            
            with col2:
                st.markdown("### Cluster Centers (Original Scale)")
                centers_df = pd.DataFrame(
                    centers_original,
                    columns=[f'MA{w}' for w in range(ma_min, ma_max + 1)],
                    index=[f'Cluster {i}' for i in range(n_clusters)]
                )
                st.dataframe(centers_df.style.format("{:.6f}"))
            
            st.markdown("### Feature Importance")
            st.markdown("The model uses moving averages of daily returns as features:")
            
            # Show feature correlations
            correlations = df_train[feature_cols].corr().iloc[0, :].sort_values(ascending=False)
            st.bar_chart(correlations)
            
            st.info(f"""
            **Interpretation:**
            - Lower cluster numbers = Lower momentum (Bearish regime)
            - Higher cluster numbers = Higher momentum (Bullish regime)
            - The model identifies {n_clusters} distinct market states based on return patterns
            - Smoothing reduces noise but maintains regime characteristics
            """)
        
        with tab4:
            st.subheader("Scale Sensitivity Analysis")
            
            # Calculate concordance
            concordance = (df_test['regime'] == df_test['regime_sem_pad']).mean() * 100
            
            st.metric(
                "Concordance between Standardized and Non-standardized",
                f"{concordance:.1f}%",
                delta="High is good" if concordance > 70 else "Low indicates scale sensitivity"
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### With Standardization")
                st.dataframe(
                    df_test['regime'].value_counts().sort_index().to_frame(),
                    use_container_width=True
                )
            
            with col2:
                st.markdown("### Without Standardization")
                st.dataframe(
                    df_test['regime_sem_pad'].value_counts().sort_index().to_frame(),
                    use_container_width=True
                )
            
            if concordance < 70:
                st.warning("⚠️ **Low Concordance Detected!**")
                st.markdown("""
                The low agreement between standardized and non-standardized methods indicates:
                - **High sensitivity to feature scaling**
                - **Standardization is essential** for this dataset
                - Without standardization, features with larger scales dominate the clustering
                
                **Recommendation:** Always use standardization for this type of analysis.
                """)
                
                # Show days with disagreement
                disagreement = df_test[df_test['regime'] != df_test['regime_sem_pad']]
                st.markdown(f"**Days with disagreement:** {len(disagreement)} ({len(disagreement)/len(df_test)*100:.1f}%)")
                st.markdown(f"**Average return on disagreement days:** {disagreement['ret_1d'].mean()*100:.4f}%")
            else:
                st.success("✅ **Good Concordance!**")
                st.markdown("""
                The high agreement between methods suggests:
                - **Robust feature relationships**
                - **Scale effects are minimal**
                - **Model is stable and reliable**
                """)
        
        # Download button for results
        st.sidebar.markdown("---")
        csv = df_test[['Close', 'regime', 'regime_suave', 'ret_1d'] + feature_cols].round(6).to_csv()
        st.sidebar.download_button(
            label="📥 Download Results (CSV)",
            data=csv,
            file_name=f"market_regimes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

else:
    # Show welcome message and instructions
    st.info("👈 **Configure parameters in the sidebar and click 'Run Analysis' to start**")
    
    st.markdown("""
    ### How it works:
    
    1. **Data Loading**: Downloads ITUB4.SA stock data from Yahoo Finance
    2. **Feature Engineering**: Creates moving averages of daily returns
    3. **Clustering**: Uses K-Means to identify market regimes
    4. **Analysis**: Visualizes regimes and calculates performance metrics
    
    ### Key Features:
    - **No look-ahead bias**: Rolling windows use only past data
    - **Scale sensitivity analysis**: Compares standardized vs non-standardized results
    - **Interactive visualizations**: Hover to see detailed information
    - **Configurable parameters**: Adjust all analysis settings
    
    ### Market Regimes:
    - **Low Momentum (Bear)**: Negative or low positive returns
    - **Medium Momentum (Neutral)**: Moderate positive returns
    - **High Momentum (Bull)**: Strong positive returns
    
    Adjust the parameters in the sidebar to customize the analysis!
    """)
    
    # Example preview
    st.markdown("---")
    st.markdown("### Sample Output Preview")
    st.image("https://via.placeholder.com/800x400?text=Interactive+Price+Chart+with+Regime+Colors", use_container_width=True)