class Day:
  def __init__(self, curr_date= None):
    self.curr_date = curr_date

  def set_curr_date(self, curr_Date): 
        self.curr_date = curr_Date

  def set_daily_temp(self,daily_temp = None):
     if isinstance(daily_temp,float):
      self.daily_temp = round(daily_temp,2)
  
  def set_evening_temp(self,evening_temp = None):
     if isinstance(evening_temp,float):
      self.evening_temp = round(evening_temp,2)

  def set_humidity(self,humidity = None):
    if isinstance(humidity,float):
      self.humidity = round(humidity,2)
     
  def to_dict(self):
        return {
            'curr_date': self.curr_date,
            'daily_temp': self.daily_temp,
            'evening_temp': self.evening_temp,
            'humidity': self.humidity
        }


      
