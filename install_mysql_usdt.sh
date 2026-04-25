#!/bin/bash

# Script de Instalação MySQL 5.7 com USDT Probes (DTrace)
# Baseado no histórico de compilação manual

set -e # Para o script se houver erro

echo "1. Instalando dependências do sistema..."
sudo apt update
sudo apt install -y cmake gcc g++ libncurses5-dev libssl-dev systemtap-sdt-dev systemtap bpftrace wget

echo "2. Baixando Código-Fonte do MySQL 5.7.44 e Boost 1.59.0..."
cd ~
# Download do MySQL Source (não o binário genérico)
wget -c https://mysql.com
# Download do Boost (evita timeout no CMake)
wget -c https://sourceforge.net

echo "3. Extraindo arquivos..."
tar -xf mysql-5.7.44.tar.gz
tar -xf boost_1_59_0.tar.gz

echo "4. Configurando compilação com suporte USDT (DTrace)..."
cd ~/mysql-5.7.44
mkdir -p build && cd build

cmake .. \
  -DENABLE_DTRACE=1 \
  -DWITH_SSL=system \
  -DWITH_BOOST=../../boost_1_59_0 \
  -DEXPLICIT_DEFAULTS_FOR_TIMESTAMP=1

echo "5. Compilando (isso pode demorar...)..."
# Usando todos os núcleos disponíveis para acelerar
make -j$(nproc)

echo "6. Instalando binários..."
sudo make install

echo "7. Configurando usuário e diretórios..."
if ! getent group mysql > /dev/null; then sudo groupadd mysql; fi
if ! getent passwd mysql > /dev/null; then sudo useradd -r -g mysql -s /bin/false mysql; fi

sudo mkdir -p /usr/local/mysql/data /usr/local/mysql/mysql-files
sudo chown -R mysql:mysql /usr/local/mysql/data /usr/local/mysql/mysql-files
sudo chmod 750 /usr/local/mysql/data /usr/local/mysql/mysql-files

echo "8. Inicializando o Banco de Dados (sem senha para teste)..."
# Removendo restos de tentativas anteriores se houver
sudo rm -rf /usr/local/mysql/data/*
sudo /usr/local/mysql/bin/mysqld --initialize-insecure --user=mysql --basedir=/usr/local/mysql --datadir=/usr/local/mysql/data

echo "9. Iniciando o MySQL Server..."
sudo /usr/local/mysql/bin/mysqld_safe --user=mysql &

# Aguarda o MySQL subir
sleep 10

echo "10. Verificando Probes USDT..."
if sudo stap -l 'process("/usr/local/mysql/bin/mysqld").mark("*")' | grep -q "query__start"; then
    echo "SUCESSO: Probes USDT detectadas!"
else
    echo "ERRO: Probes não encontradas. Verifique o log do CMake."
fi

echo "Instalação concluída em /usr/local/mysql"
echo "Para usar o cliente, execute: /usr/local/mysql/bin/mysql -u root"
