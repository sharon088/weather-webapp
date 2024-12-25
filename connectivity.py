import requests

def check_connectivity(url):  
    try:  
        response = requests.get(url)  
        if response.status_code == 200:  
            return True
        else:  
            print(f"Failed to connect to {url}. Status code: {response.status_code}")  
            return False
    except requests.exceptions.ConnectTimeout as e:
        print(f"Connection timeout for {url}. Exception: {str(e)}") 
        return False
    
    except requests.exceptions.ConnectionError as e:
        print(f"Failed to resolve hostname for {url}. Exception: {str(e)}") 
        return False 
    
    except requests.exceptions.RequestException as e:  
        print(f"Failed to connect to {url}. Exception: {str(e)}") 
        return False 


check_connectivity("http://localhost:8000/")

