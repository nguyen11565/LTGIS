from django.shortcuts import render

def home(request):
    return render(request, 'home.html')

def cart(request):
    return render(request, 'cart.html')
