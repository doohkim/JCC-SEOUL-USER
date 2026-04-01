MIDDLEWARE = [
    # "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # 내가 쓰던거
    # "subdomains.middleware.SubdomainURLRoutingMiddleware",
    
    "django.middleware.common.CommonMiddleware",
    # cursor 가 쓴거
    # "config.middleware.SubdomainRoutingMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
