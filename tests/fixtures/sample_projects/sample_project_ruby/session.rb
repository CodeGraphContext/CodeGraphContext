module Auth
  def authenticate(user)
    puts "Authenticating #{user}..."
    true
  end
end

module Notifiable
  def notify(msg)
    puts "Notification: #{msg}"
  end
end

class Session
  include Auth
  include Notifiable

  def start(user)
    if authenticate(user)
      notify("Session started for #{user}")
    end
  end
end
