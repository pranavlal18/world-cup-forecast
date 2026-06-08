# FIFA World Cup 2026 Forecasting Platform

## Overview

A live FIFA World Cup 2026 forecasting platform that predicts match outcomes using machine learning and continuously updates tournament-winning probabilities through large-scale Monte Carlo simulations as real match results arrive.

The system combines team strength ratings, historical performance, and match-level probability estimation to forecast every stage of the tournament, from the Group Stage to the Final.

## Key Features

### Match Outcome Prediction

* Predicts win, draw, and loss probabilities for every World Cup fixture.
* Uses engineered team features including Elo ratings, recent form, and team strength metrics.
* Powered by a LightGBM machine learning model.

### Monte Carlo Tournament Simulation

* Simulates the entire FIFA World Cup tournament thousands of times.
* Generates probabilities for:

  * Round of 32 qualification
  * Round of 16 qualification
  * Quarter-Final qualification
  * Semi-Final qualification
  * Final appearance
  * Tournament champion

### Dynamic Tournament Updates

* Automatically fetches official World Cup fixtures.
* Processes completed match results.
* Updates team Elo ratings after every match.
* Re-runs simulations to generate fresh tournament forecasts.

### Live Standings & Bracket Tracking

* Real-time group standings.
* Knockout bracket visualization.
* Qualification tracking across all tournament stages.

### Automated Data Pipeline

* Fixture ingestion from football-data.org.
* Elo rating updates.
* Tournament simulation pipeline.
* Probability generation and storage.
* Scheduled refresh workflow for production deployments.

---

## System Architecture

```text
Football Data API
        │
        ▼
 Fixture Collection
        │
        ▼
 Match Results Processing
        │
        ▼
 Elo Rating Updates
        │
        ▼
 Feature Engineering
        │
        ▼
 LightGBM Prediction Model
        │
        ▼
 Monte Carlo Tournament Simulation
        │
        ▼
 Probability Generation
        │
        ▼
 PostgreSQL / Supabase
        │
        ▼
 FastAPI Backend
        │
        ▼
 React Frontend
```

---

## Technology Stack

### Backend

* FastAPI
* Python
* PostgreSQL
* Supabase
* APScheduler

### Machine Learning

* LightGBM
* NumPy
* Pandas
* Scikit-Learn

### Simulation

* Monte Carlo Simulation
* Elo Rating System

### Frontend

* React
* Vite
* JavaScript

### Deployment

* Render
* Vercel
* Supabase

---

## Database Schema

### probabilities

Stores tournament advancement and championship probabilities.

```sql
team
group_letter
elo
round_of_32
round_of_16
quarter_final
semi_final
final
champion
generated_at
```

### fixtures

Stores all World Cup fixtures.

```sql
match_id
date
time_utc
stage
group_letter
team1
team2
status
```

### group_standings

Stores live group standings.

```sql
team
group_letter
played
won
drawn
lost
gf
ga
gd
points
```

### processed_matches

Tracks already-processed results to avoid duplicate Elo updates.

```sql
match_id
processed_at
```

---

## Machine Learning Pipeline

### Feature Engineering

Features include:

* Home Team Elo
* Away Team Elo
* Elo Difference
* Team Form Metrics
* Historical Match Statistics
* Injury Indicators
* Tournament Context Features

### Model Output

The model predicts:

```text
P(Home Win)
P(Draw)
P(Away Win)
```

These probabilities are then used as inputs for tournament simulation.

---

## Monte Carlo Simulation

For every simulation run:

1. Group-stage matches are simulated.
2. Group standings are calculated.
3. Qualified teams advance.
4. Knockout rounds are simulated.
5. Tournament winner is recorded.

The process is repeated thousands of times.

Example:

```text
10,000 Simulations

Spain        Champion: 22.7%
Argentina    Champion: 16.4%
France        Champion: 8.0%
Colombia      Champion: 6.3%
Brazil        Champion: 6.2%
```

---

## API Endpoints

### Tournament Probabilities

```http
GET /api/pipeline/
```

Returns tournament probabilities for all teams.

### Group Standings

```http
GET /api/groups/
```

Returns live group standings.

### Bracket

```http
GET /api/bracket/
```

Returns knockout bracket information.

### Fixtures

```http
GET /api/matches/
```

Returns tournament fixtures.

### Status

```http
GET /api/status
```

Returns pipeline and simulation status.

---

## Local Setup

### Clone Repository

```bash
git clone <repository-url>
cd world-cup-forecast
```

### Backend Setup

```bash
python -m venv .venv

source .venv/bin/activate
# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

### Frontend Setup

```bash
cd frontend

npm install

npm run dev
```

### Run Backend

```bash
uvicorn backend.main:app --reload
```

---

## Running the Pipeline

### Fetch Latest Fixtures

```bash
python -m pipeline.api_client --cache
```

### Run Tournament Simulation

```bash
python -m pipeline.run_pipeline --force
```

### Update Elo Ratings

```bash
python -m pipeline.update_elo
```

---

## Production Workflow

```text
Every 15 Minutes

Fetch Fixtures
      ↓
Fetch Completed Matches
      ↓
Update Elo Ratings
      ↓
Run Monte Carlo Simulations
      ↓
Update Probabilities
      ↓
Refresh Frontend
```

---

## Future Improvements

* Player-level injury modelling
* Expected Goals (xG) integration
* Bayesian Elo updates
* Ensemble prediction models
* Real-time live match forecasting
* Explainable AI probability insights
* Tournament scenario explorer

---

## Project Highlights

* End-to-end machine learning forecasting system
* Automated sports analytics pipeline
* Real-time probability updates
* Monte Carlo tournament simulation engine
* Production-ready full-stack architecture
* Scalable cloud deployment using Render, Vercel, and Supabase

---

## Author

Pranav Lal

Software Engineering | Machine Learning | Sports Analytics
