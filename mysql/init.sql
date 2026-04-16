-- Banco de dados de laboratório BCC
-- Criado automaticamente na inicialização do container MySQL

USE lab;

-- Tabela de produtos para queries de leitura
CREATE TABLE IF NOT EXISTS produtos (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    nome       VARCHAR(100) NOT NULL,
    categoria  VARCHAR(50)  NOT NULL,
    preco      DECIMAL(10,2) NOT NULL,
    estoque    INT NOT NULL DEFAULT 0,
    criado_em  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_categoria (categoria),
    INDEX idx_preco (preco)
) ENGINE=InnoDB;

-- Tabela de pedidos para queries com JOIN
CREATE TABLE IF NOT EXISTS pedidos (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    produto_id    INT NOT NULL,
    quantidade    INT NOT NULL,
    valor_total   DECIMAL(10,2) NOT NULL,
    status        ENUM('pendente', 'processando', 'concluido', 'cancelado') DEFAULT 'pendente',
    criado_em     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (produto_id) REFERENCES produtos(id),
    INDEX idx_status (status),
    INDEX idx_criado_em (criado_em)
) ENGINE=InnoDB;

-- Tabela de eventos para rastreamento de tráfego gerado
CREATE TABLE IF NOT EXISTS eventos_trace (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    tipo       VARCHAR(30) NOT NULL,
    descricao  VARCHAR(255),
    criado_em  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Seed: 200 produtos
INSERT INTO produtos (nome, categoria, preco, estoque) VALUES
('Notebook Dell XPS 15', 'Eletrônicos', 7999.99, 15),
('Monitor LG 27"', 'Eletrônicos', 1499.99, 30),
('Teclado Mecânico Keychron', 'Periféricos', 549.90, 50),
('Mouse Logitech MX Master', 'Periféricos', 399.90, 45),
('Headset Sony WH-1000XM5', 'Áudio', 1799.99, 20),
('SSD Samsung 1TB', 'Armazenamento', 449.90, 60),
('Webcam Logitech C920', 'Periféricos', 699.99, 25),
('Hub USB-C Anker', 'Periféricos', 199.90, 80),
('Suporte para Monitor', 'Acessórios', 149.90, 100),
('Cadeira Gamer DXRacer', 'Móveis', 2499.99, 10),
('Mesa Ajustável Flexispot', 'Móveis', 1899.99, 8),
('Iluminação LED RGB', 'Acessórios', 89.90, 200),
('Carregador 65W GaN', 'Acessórios', 179.90, 75),
('Cabo HDMI 4K 2m', 'Cabos', 49.90, 150),
('Switch KVM 4 portas', 'Rede', 349.90, 18),
('Roteador Asus AX5400', 'Rede', 899.99, 22),
('Raspberry Pi 4 8GB', 'Computadores', 599.99, 12),
('Arduino Mega 2560', 'Eletrônicos', 149.99, 35),
('Impressora 3D Creality', 'Impressão', 1299.99, 7),
('Controlador PID Autonics', 'Industrial', 299.99, 5);

-- Gera mais 180 produtos variados via procedure
DELIMITER $$
CREATE PROCEDURE seed_produtos()
BEGIN
    DECLARE i INT DEFAULT 21;
    DECLARE categorias VARCHAR(200) DEFAULT 'Eletrônicos,Periféricos,Rede,Armazenamento,Acessórios';
    WHILE i <= 200 DO
        INSERT INTO produtos (nome, categoria, preco, estoque)
        VALUES (
            CONCAT('Produto Lab #', i),
            ELT(1 + MOD(i, 5), 'Eletrônicos', 'Periféricos', 'Rede', 'Armazenamento', 'Acessórios'),
            ROUND(10 + RAND() * 990, 2),
            FLOOR(5 + RAND() * 195)
        );
        SET i = i + 1;
    END WHILE;
END$$
DELIMITER ;

CALL seed_produtos();
DROP PROCEDURE IF EXISTS seed_produtos;

-- Seed: 100 pedidos
INSERT INTO pedidos (produto_id, quantidade, valor_total, status)
SELECT
    id,
    FLOOR(1 + RAND() * 5),
    preco * FLOOR(1 + RAND() * 5),
    ELT(FLOOR(1 + RAND() * 4), 'pendente', 'processando', 'concluido', 'cancelado')
FROM produtos
LIMIT 100;
