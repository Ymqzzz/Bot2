# Multi-Layer Quant Trading System Architecture

## Core Idea
This system ingests market, macro, and behavioral data; transforms it into strategy signals; then executes only risk-approved trades.

Every concept in the stack must have an explicit role:
- Input data
- Feature
- Model
- Signal
- Regime detector
- Execution logic
- Risk control
- Portfolio logic
- Surveillance
- Backtest/validation metric

If a concept does not map to one of these roles, it is out of scope.

## End-to-End Pipeline

```text
DATA -> FEATURES -> STRATEGIES -> SIGNALS
         |             |            |
         +-------------+------------+
                       |
                    REGIME
                       |
                WEIGHTING ENGINE
                       |
             PORTFOLIO ALLOCATION
                       |
                  RISK CHECKS
                       |
                   EXECUTION
                       |
                     TRADE
```

A trade is placed only if all layers approve.

## Layer Responsibilities

1. **Data layer**
   - Sources: market data, order book, macro, sentiment, derivatives, execution telemetry.
   - Output: cleaned, timestamp-aligned datasets.

2. **Feature layer**
   - Converts raw inputs into model-ready quantities.
   - Examples: microprice, imbalance, RSI, realized volatility, spread cost.

3. **Strategy layer**
   - Independent strategy families produce trade hypotheses.
   - Output per strategy: `direction`, `strength`, `confidence`, and rationale metadata.

4. **Regime layer**
   - Classifies current market condition (trend/range/high-vol/crisis/etc).
   - Regime gates strategy eligibility and influences sizing/weighting.

5. **Weighting layer (adaptive confluence)**
   - Combines strategy outputs using:
     - recent strategy performance
     - current regime fit
     - confidence calibration
     - cross-strategy correlation/overlap

6. **Portfolio layer**
   - Converts weighted intent into allocatable risk and exposure.
   - Handles diversification, concentration limits, and capital budgets.

7. **Risk layer**
   - Hard guards: drawdown, VaR, leverage, liquidity, exposure, kill-switches.
   - Can reduce or block orders regardless of upstream conviction.

8. **Execution layer**
   - Chooses order style and scheduling: market/limit, TWAP/VWAP, slicing, route selection.
   - Minimizes slippage and adverse selection.

9. **Surveillance layer**
   - Detects toxic flow/manipulation/liquidity traps.
   - Can downgrade confidence, alter tactics, or trigger risk escalation.

## Engine Modules and Their Jobs

### 1) Microstructure Engine
Short-horizon pressure and fill-quality estimation.
- Inputs: order book depth, spread, queue dynamics.
- Typical outputs: microprice tilt, fill probability, near-term pressure.

### 2) Order Flow Engine
Aggressive participation and absorption signals.
- Inputs: trade prints, signed volume, footprint features.
- Typical outputs: delta pressure, absorption flags, VPIN-like toxicity.

### 3) Market Structure Engine
Liquidity map and structural breaks.
- Inputs: swing structure, liquidity pools, imbalance zones.
- Typical outputs: BOS/CHoCH states, sweep likelihood, structure bias.

### 4) Technical Engine
Low-cost baseline trend/mean-reversion indicators.
- Inputs: OHLCV.
- Typical outputs: RSI, MACD, moving-average regimes.

### 5) Statistical Engine
Model-based alpha and state estimation.
- Inputs: returns/spreads/features.
- Typical outputs: reversion scores, ARIMA residuals, cointegration signals, Kalman states.

### 6) Volatility Engine
Volatility state and expansion/contraction risk.
- Inputs: realized/implicit vol proxies.
- Typical outputs: vol regime, shock probability, risk multipliers.

### 7) Derivatives Engine
Positioning and convexity-aware context.
- Inputs: open interest, gamma proxies, skew/term structure.
- Typical outputs: dealer pressure bias, squeeze risk, regime modifiers.

### 8) Macro Engine
Top-down environment filter.
- Inputs: rates, liquidity, credit/risk sentiment.
- Typical outputs: macro risk-on/off state, factor tilts.

### 9) Behavioral Engine
Crowd/positioning distortions.
- Inputs: sentiment, retail flow proxies, panic/FOMO indicators.
- Typical outputs: contrarian or momentum behavioral modifiers.

### 10) Regime Engine (central coordinator)
System-wide context selection.
- Inputs: cross-engine state vectors.
- Typical outputs: regime label + confidence + transition risk.

### 11) Portfolio Engine
Capital and risk budget assignment.
- Inputs: weighted signal book + risk budgets.
- Typical outputs: target notional, per-strategy allocation, diversification adjustments.

### 12) Risk Engine (guardrail)
Capital preservation and policy enforcement.
- Inputs: portfolio targets + live risk metrics.
- Typical outputs: allow/reduce/block decisions and reason codes.

### 13) Execution Engine
Tactical implementation.
- Inputs: approved orders + liquidity conditions.
- Typical outputs: child-order plan, routing policy, execution quality metrics.

### 14) Surveillance Engine
Market integrity and toxicity defense.
- Inputs: flow anomalies, spoof-like patterns, liquidity traps.
- Typical outputs: toxicity score, guardrail triggers, execution constraints.

## Role Mapping Examples

- Gamma exposure -> regime conditioning + risk throttling
- VPIN/toxicity -> execution filtering + surveillance escalation
- Kelly fraction -> portfolio sizing
- Hurst exponent -> regime detection
- Moving averages -> trend feature input
- Spread/queue stats -> execution cost filter

## Implementation Contract
Each engine must expose:
- `inputs_required`
- `features_emitted`
- `signals_emitted` (if applicable)
- `risk_hooks`
- `regime_dependencies`
- `confidence_schema`
- `reason_codes`

This contract prevents concept creep and keeps every model artifact attributable.

## Validation Requirements
At minimum, each layer should be validated with:
- Unit tests for feature/model correctness
- Replay/backtest checks by regime segment
- Correlation overlap checks between strategies
- Execution slippage and fill-quality benchmarks
- Risk policy assertion tests (block/allow paths)
- Reason-code coverage for all block/override branches

## Non-Goals
- Adding indicators without an explicit role
- Allowing unbounded strategy voting without correlation controls
- Bypassing risk/surveillance for "high confidence" trades

## One-Line Mental Model
The system is not "all signals at once"; it is role-based orchestration where data becomes constrained, risk-aware execution.
