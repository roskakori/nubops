set -e
systemctl restart ${project}
ln -s /etc/nginx/sites-available/${domain} /etc/nginx/sites-enabled
# TODO: certbot --agree-tos -d ${domain} -n --nginx
systemctl restart nginx
