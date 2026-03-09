#!/bin/bash
# Скрипт для автоматического push изменений в 
# /home/rutra/vip на GitHub Переходим в папку проекта
cd /home/rutra/vip || { echo "Папка не найдена"; exit 
1; }
# Проверяем SSH-соединение с GitHub
ssh -T git@github.com &> /dev/null if [ $? -ne 1 ]; 
then
    echo "Ошибка SSH соединения с GitHub!" exit 1 fi
# Подтягиваем последние изменения
git pull origin main
# Добавляем все файлы
git add .
# Запрашиваем сообщение коммита
read -p "Введите сообщение коммита: " commit_msg if [ 
-z "$commit_msg" ]; then
    commit_msg="Update from server" fi
# Создаём коммит
git commit -m "$commit_msg"
# Пушим на GitHub
git push origin main
echo "Все изменения успешно отправлены на GitHub!"
