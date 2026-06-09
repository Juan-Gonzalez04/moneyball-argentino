-- Crear extensiones
CREATE EXTENSION IF NOT EXISTS uuid-ossp;

-- Tabla de equipos
CREATE TABLE IF NOT EXISTS teams (
    team_id SERIAL PRIMARY KEY,
    afa_id INT UNIQUE,
    name VARCHAR(100) NOT NULL,
    city VARCHAR(50),
    founded_year INT,
    created_at TIMESTAMP DEFAULT NOW(),     
    updated_at TIMESTAMP DEFAULT NOW()
    );

    -- Tabla de jugadores 
    CREATE TABLE IF NOT EXISTS players (     
        player_id INT PRIMARY KEY,     
        afa_id INT,     
        first_name VARCHAR(100),     
        last_name VARCHAR(100),     
        nick_name VARCHAR(100),     
        birth_date DATE,     
        age INT,     
        nationality VARCHAR(50),     
        height INT,     
        weight INT,     
        position_id INT,     
        current_team_id INT REFERENCES teams(team_id),     
        created_at TIMESTAMP DEFAULT NOW(),     
        updated_at TIMESTAMP DEFAULT NOW() 
        ); 

    -- Tabla de goles 
    CREATE TABLE IF NOT EXISTS player_goals (     
        player_id INT REFERENCES players(player_id),     
        season_year INT,     
        team_id INT REFERENCES teams(team_id),     
        total_goals INT,     
        head_goals INT,     
        free_kick_goals INT,     
        penalty_goals INT,     
        created_at TIMESTAMP DEFAULT NOW(),     
        PRIMARY KEY (player_id, season_year) 
        ); 

    -- Índices para queries rápidas 
    CREATE INDEX idx_players_age ON players(age); 
    CREATE INDEX idx_players_team ON players(current_team_id); 
    CREATE INDEX idx_goals_season ON player_goals(season_year);
