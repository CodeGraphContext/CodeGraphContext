import Foundation

let bot = Robot(name: "CGC-Bot", model: "v1")
let boss = Supervisor<Robot>()
boss.announce(item: bot)
