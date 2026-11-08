-- ==============================================================================
-- MoneyBall Argentino / Argos - Definición del Esquema Relacional (DDL)
-- Motor: PostgreSQL 15+
-- Estrategia: Persistencia Híbrida (Relacional Normalizado + Columnas JSONB)
-- ==============================================================================

-- 1. Extensiones
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Tabla: Equipos (Teams)
-- Mapea directamente el teamId numérico de AFA como Primary Key (ej. Belgrano = 124)
CREATE TABLE IF NOT EXISTS teams (
    team_id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    short_name VARCHAR(50),
    team_type VARCHAR(50) DEFAULT 'club',
    colors JSONB,
    raw_payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Tabla: Jugadores (Players)
-- Identidad del futbolista, biometría y asignación de plantel
CREATE TABLE IF NOT EXISTS players (
    player_id INT PRIMARY KEY,
    team_id INT REFERENCES teams(team_id) ON DELETE SET NULL,
    squad_no INT,
    position_id INT,
    first_name VARCHAR(100),
    middle_name VARCHAR(100),
    last_name VARCHAR(100),
    nick_name VARCHAR(100),
    birth_date DATE,
    age INT,
    height INT, -- en centímetros (ej. 178)
    weight INT, -- en kilogramos (ej. 70)
    nationality VARCHAR(50),
    current_team_name VARCHAR(100),
    raw_payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Tabla: Estadísticas de Goles (Player Goals)
-- Desglose minucioso de anotaciones por jugador y temporada
CREATE TABLE IF NOT EXISTS player_goals (
    player_id INT REFERENCES players(player_id) ON DELETE CASCADE,
    season_year INT NOT NULL,
    total_goals INT DEFAULT 0,
    played_goals INT DEFAULT 0,
    first_time_goals INT DEFAULT 0,
    second_time_goals INT DEFAULT 0,
    head_goals INT DEFAULT 0,
    free_kick_goals INT DEFAULT 0,
    penalty_goals INT DEFAULT 0,
    raw_payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (player_id, season_year)
);

-- 5. Tabla: Estadísticas de Rendimiento (Player Stats)
-- Minutos jugados, tiros, pases, recuperaciones y disciplina
CREATE TABLE IF NOT EXISTS player_stats (
    player_id INT REFERENCES players(player_id) ON DELETE CASCADE,
    season_year INT NOT NULL,
    minutes_total INT DEFAULT 0,
    minutes_holds INT DEFAULT 0,
    minutes_substitute INT DEFAULT 0,
    shots_total INT DEFAULT 0,
    shots_on_target INT DEFAULT 0,
    shots_off_target INT DEFAULT 0,
    shots_woodwork INT DEFAULT 0,
    passes_correct INT DEFAULT 0,
    passes_incorrect INT DEFAULT 0,
    fouls_committed INT DEFAULT 0,
    fouls_received INT DEFAULT 0,
    yellow_cards INT DEFAULT 0,
    double_yellow_cards INT DEFAULT 0,
    red_cards INT DEFAULT 0,
    steals_total INT DEFAULT 0,
    goal_assistances INT DEFAULT 0,
    saves_total INT DEFAULT 0,
    raw_payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (player_id, season_year)
);

-- ==============================================================================
-- 6. Tabla: Estadísticas Oficiales de Clubes (Team Stats)
-- ==============================================================================
-- Métricas colectivas institucionales canónicas (partidos, goles reales,
-- tiros, posesión/pases, efectividad y disciplina)
CREATE TABLE IF NOT EXISTS team_stats (
    team_id INT REFERENCES teams(team_id) ON DELETE CASCADE,
    season_year INT NOT NULL,
    matches_played INT DEFAULT 0,
    matches_won INT DEFAULT 0,
    matches_drawn INT DEFAULT 0,
    matches_lost INT DEFAULT 0,
    points INT DEFAULT 0,
    goals_for INT DEFAULT 0,
    goals_first_half INT DEFAULT 0,
    goals_second_half INT DEFAULT 0,
    goals_head INT DEFAULT 0,
    goals_penalty INT DEFAULT 0,
    goals_freekick INT DEFAULT 0,
    goals_own INT DEFAULT 0,
    shots_total INT DEFAULT 0,
    shots_on_target INT DEFAULT 0,
    shots_off_target INT DEFAULT 0,
    shots_woodwork INT DEFAULT 0,
    conversion_rate_pct NUMERIC(5,2) DEFAULT 0.0,
    passes_correct INT DEFAULT 0,
    passes_incorrect INT DEFAULT 0,
    passes_total INT DEFAULT 0,
    pass_accuracy_pct NUMERIC(5,2) DEFAULT 0.0,
    fouls_committed INT DEFAULT 0,
    fouls_received INT DEFAULT 0,
    yellow_cards INT DEFAULT 0,
    double_yellow_cards INT DEFAULT 0,
    red_cards INT DEFAULT 0,
    steals_total INT DEFAULT 0,
    corner_kicks INT DEFAULT 0,
    offsides INT DEFAULT 0,
    goal_assistances INT DEFAULT 0,
    raw_payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (team_id, season_year)
);

-- ==============================================================================
-- 7. Índices para Aceleración de Consultas de Scouting y Métricas
-- ==============================================================================

-- B-Tree para filtros rápidos por edad, equipo y posición
CREATE INDEX IF NOT EXISTS idx_players_age ON players(age);
CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id);
CREATE INDEX IF NOT EXISTS idx_players_position ON players(position_id);

-- Índices para métricas de rendimiento y scouting Sub-23
CREATE INDEX IF NOT EXISTS idx_stats_minutes ON player_stats(minutes_total);
CREATE INDEX IF NOT EXISTS idx_goals_total ON player_goals(total_goals);

-- Índices para métricas institucionales de clubes
CREATE INDEX IF NOT EXISTS idx_team_stats_points ON team_stats(points);
CREATE INDEX IF NOT EXISTS idx_team_stats_goals_for ON team_stats(goals_for);

-- Índice GIN para búsquedas y consultas arbitrarias sobre el payload JSONB
CREATE INDEX IF NOT EXISTS idx_players_raw_payload_gin ON players USING gin(raw_payload);
CREATE INDEX IF NOT EXISTS idx_teams_raw_payload_gin ON teams USING gin(raw_payload);
CREATE INDEX IF NOT EXISTS idx_team_stats_raw_payload_gin ON team_stats USING gin(raw_payload);
