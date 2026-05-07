CREATE TABLE IF NOT EXISTS food_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    price DECIMAL(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    item_id INT NOT NULL,
    quantity INT NOT NULL,
    total_price DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (item_id) REFERENCES food_items(id)
);

INSERT INTO food_items (name, price) VALUES
    ('Cold Coffee', 120.00),
    ('Pasta', 180.00),
    ('French Fries', 100.00),
    ('Chicken Biryani', 250.00),
    ('Masala Dosa', 80.00),
    ('Paneer Wrap', 150.00),
    ('Chocolate Shake', 130.00),
    ('Veg Burger', 110.00)
ON DUPLICATE KEY UPDATE name = name;
