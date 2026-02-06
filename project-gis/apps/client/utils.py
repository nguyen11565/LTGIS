import math

def haversine_distance(lat1, lon1, lat2, lon2):
    # Bán kính trái đất (km)
    R = 6371.0
    
    # Chuyển đổi độ sang radian
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return distance # Đơn vị: km