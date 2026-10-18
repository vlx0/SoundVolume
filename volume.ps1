Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class VolumeKey {
    [DllImport("user32.dll")]
    private static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, IntPtr dwExtraInfo);

    private const byte VK_VOLUME_MUTE = 0xAD;
    private const byte VK_VOLUME_DOWN = 0xAE;
    private const byte VK_VOLUME_UP = 0xAF;
    private const uint KEYEVENTF_EXTENDEDKEY = 0x0001;
    private const uint KEYEVENTF_KEYUP = 0x0002;

    public static void Tap(byte vk) {
        keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY, IntPtr.Zero);
        keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, IntPtr.Zero);
    }
    public static void Mute()   { Tap(VK_VOLUME_MUTE); }
    public static void VolDown(){ Tap(VK_VOLUME_DOWN); }
    public static void VolUp()  { Tap(VK_VOLUME_UP); }
}
"@ -ErrorAction Stop

function Step($count, $dir) {
    $cap = [Math]::Min([int]$count, 50)
    if ($cap -le 0) { return }
    $method = if ($dir -eq 'up') { 'VolUp' } else { 'VolDown' }
    for ($i = 0; $i -lt $cap; $i++) {
        [VolumeKey]::$method() | Out-Null
    }
}

if ($args.Count -lt 2) { Write-Output "usage: -Action up|down|mute|set -N <int>"; exit 2 }
$act = $args[0]; $n = [int]$args[1]

switch ($act) {
    'up'   { Step $n 'up' }
    'down' { Step $n 'down' }
    'mute' { [VolumeKey]::Mute() }
    default { Write-Output "bad action"; exit 2 }
}
$out = "OK:" + $act + ":" + $n
Write-Output $out