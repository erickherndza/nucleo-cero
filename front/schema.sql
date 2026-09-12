CREATE TABLE trabajos (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  token_publico   CHAR(32) NOT NULL UNIQUE,
  cliente_email   VARCHAR(255) NOT NULL,
  estado          ENUM('pendiente','reclamado','procesando','listo','error')
                  NOT NULL DEFAULT 'pendiente',
  factor          DECIMAL(3,1) NOT NULL DEFAULT 2.0,
  params_json     TEXT,
  worker_id       VARCHAR(64),
  intentos        TINYINT NOT NULL DEFAULT 0,
  error_msg       TEXT,
  metricas_json   TEXT,
  creado_en       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  iniciado_en     DATETIME,
  terminado_en    DATETIME,
  purgar_en       DATETIME,
  INDEX idx_estado (estado, creado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE archivos (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  trabajo_id  INT NOT NULL,
  tipo        ENUM('origen','resultado','informe') NOT NULL,
  nombre      VARCHAR(255) NOT NULL,
  ruta        VARCHAR(512) NOT NULL,
  bytes       BIGINT NOT NULL,
  sha256      CHAR(64),
  creado_en   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (trabajo_id) REFERENCES trabajos(id) ON DELETE CASCADE,
  INDEX idx_trabajo (trabajo_id, tipo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
