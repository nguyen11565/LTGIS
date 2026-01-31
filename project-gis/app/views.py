from django.shortcuts import render


def home(request):
    return render(request, "app/home.html")


def cart(request):
    return render(request, "app/cart.html")