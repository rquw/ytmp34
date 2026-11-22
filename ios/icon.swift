import AppKit

// draws the 1024px app icon: a prism splitting a white beam into the train-line colours
let s: CGFloat = 1024
let img = NSImage(size: NSSize(width: s, height: s))
img.lockFocus()
let ctx = NSGraphicsContext.current!.cgContext
ctx.setFillColor(NSColor(calibratedRed: 0.07, green: 0.06, blue: 0.10, alpha: 1).cgColor)
ctx.fill(CGRect(x: 0, y: 0, width: s, height: s))

let a = CGPoint(x: 512, y: 760), b = CGPoint(x: 300, y: 330), c = CGPoint(x: 724, y: 330)
// incoming beam
ctx.setStrokeColor(NSColor.white.cgColor)
ctx.setLineWidth(26)
ctx.setLineCap(.round)
ctx.move(to: CGPoint(x: 90, y: 470)); ctx.addLine(to: CGPoint(x: 420, y: 540)); ctx.strokePath()
// spectrum out
let cols: [NSColor] = [.systemRed, .systemOrange, .systemYellow, .systemGreen, .systemBlue, .systemPurple]
for (i, col) in cols.enumerated() {
    ctx.setStrokeColor(col.cgColor)
    ctx.setLineWidth(30)
    let y0 = 520 - CGFloat(i) * 14, y1 = 640 - CGFloat(i) * 70
    ctx.move(to: CGPoint(x: 610, y: y0)); ctx.addLine(to: CGPoint(x: 960, y: y1)); ctx.strokePath()
}
// the prism
ctx.setFillColor(NSColor(calibratedWhite: 1, alpha: 0.10).cgColor)
ctx.setStrokeColor(NSColor.white.cgColor)
ctx.setLineWidth(22)
ctx.setLineJoin(.round)
ctx.move(to: a); ctx.addLine(to: b); ctx.addLine(to: c); ctx.closePath()
ctx.drawPath(using: .fillStroke)
img.unlockFocus()

let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
