CREATE DATABASE IF NOT EXISTS combine CHARACTER SET utf8 COLLATE utf8_general_ci;
CREATE USER IF NOT EXISTS 'combine'@'%' IDENTIFIED BY 'combine';
GRANT ALL PRIVILEGES ON * . * TO 'combine'@'%';
FLUSH PRIVILEGES;