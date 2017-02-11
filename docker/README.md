[dockers]
docker01.local
docker02.local
docker03.local

# add current user to group `wheel`

    sudo usermod `whoami` -g wheel

# make `sudo` without password

    # %wheel        ALL=(ALL)       ALL
    %wheel  ALL=(ALL)       NOPASSWD: ALL