import telebot
import requests
import shutil
import subprocess
import os.path

API_TOKEN = ''
bot = telebot.TeleBot(5528327030:AAEOK4rjHVN-sczJyVECSV0dpacX8Ao93Iw)
settings = {}
enabled = []

def isEnabled(id):
  return id in enabled if len(enabled)>0 else True

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
  if isEnabled(message.chat.id):
      bot.reply_to(message, "Hi send me a photo (with square aspect ratio), you will then be able to use this face\n"
    "Switch output between video mode and video note mode with /output\nSwitch relative position with /relative\n\nIssues with speed?\nChange to dynamic mode with /speed")

def get(key,id_utente,default_value=False):
  if not id_utente in settings:
    settings[id_utente]={}
  if not key in settings[id_utente]:
    settings[id_utente][key]=default_value
  return settings[id_utente][key]

def set(key,value,id_utente):
  get(key,id_utente) #init
  settings[id_utente][key]=value

#fix for wrong length speedup on OnePlus
def get_length(filename):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of",
                             "default=noprint_wrappers=1:nokey=1", filename],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    return float(result.stdout)

@bot.message_handler(commands=['output'])
def videomode(message):
  if isEnabled(message.chat.id):
    if get('mode',message.chat.id):
      set('mode',False,message.chat.id)
    else:
      set('mode',True,message.chat.id)
    bot.reply_to(message, "I've changed mode correctly.")

@bot.message_handler(commands=['speed'])
def speedmode(message):
  if isEnabled(message.chat.id):
    if get('dynamic_scale',message.chat.id):
      set('dynamic_scale',False,message.chat.id)
    else:
      set('dynamic_scale',True,message.chat.id)
    bot.reply_to(message, "I've changed the speed adaptation correctly.")

@bot.message_handler(commands=['relative'])
def relativemode(message):
  if isEnabled(message.chat.id):
    if get('relative',message.chat.id,default_value=True):
      set('relative',False,message.chat.id)
    else:
      set('relative',True,message.chat.id)
    bot.reply_to(message, f"I've changed the relative mode to {get('relative',message.chat.id)} correctly.")

@bot.message_handler(content_types=['photo'])
def download_pic(message):
  if isEnabled(message.chat.id):
    file_info = bot.get_file([ph.file_id for ph in message.photo if ph.file_size== max([photo.file_size for photo in message.photo])][0])
    file = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(API_TOKEN, file_info.file_path))
    id = message.chat.id;
    open(f'../src{id}.jpg', 'wb').write(file.content)
    bot.reply_to(message, "Perfect, now send me a video note or a video! (for best results keep head movements to a minimum and keep a static background)")

@bot.message_handler(content_types=['video_note','video'])
def download_video(message):
  if isEnabled(message.chat.id):
    try:
      id = message.chat.id;
      file_info = bot.get_file(message.video_note.file_id if message.content_type == 'video_note' else message.video.file_id)
      print('https://api.telegram.org/file/bot{0}/{1}'.format(API_TOKEN, file_info.file_path));
      file = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(API_TOKEN, file_info.file_path))
      open(f'../target{id}.mp4', 'wb').write(file.content)
      #extract audio
      subprocess.call(['ffmpeg', '-i', f'../target{id}.mp4', '-vn', '-acodec','copy', f'../out{id}.aac'])
      if os.path.exists(f'../src{id}.jpg'):
        bot.reply_to(message, "I'm generating the deep fake...")
        bot.send_chat_action(id, 'record_video')
        source_image = imageio.imread(f'../src{id}.jpg')
        source_image = resize(source_image, (256, 256))[..., :3]
      else:
        bot.reply_to(message, "You have to send me an image first!")
        return
      try:
        driving_video = imageio.mimread(f'../target{id}.mp4')
      except Exception as e:
        reader = imageio.get_reader(f'../target{id}.mp4')
        driving_video = []
        try:
            for im in reader:
                driving_video.append(im)
        except RuntimeError:
            pass
      driving_video = [resize(frame, (256, 256))[..., :3] for frame in driving_video]
      predictions = make_animation(source_image, driving_video, generator, kp_detector, relative=get('relative',message.chat.id,default_value=True),cpu=cpu)
      imageio.mimsave(f'../generated{id}.mp4', [img_as_ubyte(frame) for frame in predictions])
      #normal speed
      if get('dynamic_scale',message.chat.id):
        dynamic_scale=1/(get_length(f'../generated{id}.mp4')/get_length(f'../target{id}.mp4'))
      else:
        dynamic_scale=0.33334

      subprocess.call(['ffmpeg', '-itsscale',f'{dynamic_scale}', '-i', f'../generated{id}.mp4', '-c','copy', f'../generated_fast{id}.mp4'])
      print(get_length(f'../generated_fast{id}.mp4'))
      #add audio
      subprocess.call(['ffmpeg', '-i', f'../generated_fast{id}.mp4', '-i',f'../out{id}.aac', '-c', 'copy','-map','0:v:0','-map','1:a:0', f'../tosend{id}.mp4'])
      videonote = open(f'../tosend{id}.mp4', 'rb')
      if get('mode',message.chat.id):
        bot.send_video(id, videonote)
      else:
        bot.send_video_note(id,videonote)
    finally:
      #cleanup
      if os.path.exists(f'../target{id}.mp4'):
        os.remove(f'../target{id}.mp4')
      if os.path.exists(f'../generated{id}.mp4'):
        os.remove(f'../generated{id}.mp4')
      if os.path.exists(f'../generated_fast{id}.mp4'):
        os.remove(f'../generated_fast{id}.mp4')
      if os.path.exists(f'../tosend{id}.mp4'):
        os.remove(f'../tosend{id}.mp4')
      if os.path.exists(f'../out{id}.aac'):
        os.remove(f'../out{id}.aac')
      if os.path.exists(f'../src{id}.jpg'):
        os.remove(f'../src{id}.jpg')

bot.polling()
