apt update && apt upgrade -y
apt install python make wget termux-exec clang libjpeg-turbo freetype -y
env INCLUDE="$PREFIX/include" LDFLAGS=" -lm" pip install Pillow