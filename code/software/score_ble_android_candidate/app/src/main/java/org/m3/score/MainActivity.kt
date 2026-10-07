package org.m3.score

import android.Manifest
import android.app.Activity
import android.bluetooth.*
import android.bluetooth.le.*
import android.content.Intent
import android.content.pm.PackageManager
import android.os.*
import android.widget.*
import java.util.UUID
import java.util.ArrayDeque

/** Foreground-only minimal candidate. No audio, network, background service or auto target. */
@Suppress("DEPRECATION", "MissingPermission")
class MainActivity : Activity(), Protocol.Sink {
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var info: TextView
    private lateinit var devices: LinearLayout
    private val rawLog = StringBuilder()
    private val seen = mutableSetOf<String>()
    private var gatt: BluetoothGatt? = null
    private var rx: BluetoothGattCharacteristic? = null
    private var ready = false
    private var score: Protocol.Score? = null
    private var client = Protocol.Session(this)
    private val frames = ArrayDeque<ByteArray>()
    private var writing: ByteArray? = null
    private var offset = 0
    private var writeDue = 0L
    private var sessionNumber = 1
    private var scanning = false
    private var selectedAddress: String? = null
    private val adapter: BluetoothAdapter? get() = getSystemService(BluetoothManager::class.java)?.adapter
    private val cccd = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")
    private fun log(text: String) {
        if (rawLog.length + text.length < 4 * 1024 * 1024) rawLog.append(SystemClock.elapsedRealtime()).append(' ').append(text).append('\n')
        info.text = text
    }
    override fun state(message: String) { log(message) }
    override fun send(raw: ByteArray) {
        if (!ready || frames.size >= 2) { client.fail("LOCAL_NOT_READY_OR_BUSY"); return }
        frames.add(raw.copyOf()); nextFrame()
    }
    private fun nextFrame() {
        if (writing != null || frames.isEmpty()) return
        writing = frames.removeFirst(); offset = 0; writeDue = SystemClock.elapsedRealtime() + 1500; writeFragment()
    }
    private fun writeFragment() {
        val bytes = writing ?: return
        val characteristic = rx ?: return
        val connection = gatt ?: return
        characteristic.writeType = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
        characteristic.value = bytes.copyOfRange(offset, minOf(offset + 20, bytes.size))
        if (!connection.writeCharacteristic(characteristic)) stop("LOCAL_GATT_WRITE_REJECT")
    }
    private fun stop(reason: String) {
        ready = false; frames.clear(); writing = null; rx = null
        client.fail(reason); gatt?.disconnect(); gatt?.close(); gatt = null; log(reason)
    }
    private val clock = object : Runnable {
        override fun run() {
            val now = SystemClock.elapsedRealtime()
            client.tick(now)
            if (writing != null && now >= writeDue) stop("LOCAL_GATT_WRITE_TIMEOUT")
            handler.postDelayed(this, 50)
        }
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        sessionNumber = getPreferences(MODE_PRIVATE).getInt("next_session", 1)
        val layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(16,16,16,16) }
        info = TextView(this); devices = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        fun button(label: String, action: () -> Unit) { layout.addView(Button(this).apply { text = label; setOnClickListener { try { action() } catch (e: Exception) { log("LOCAL ${e.message}") } } }) }
        button("导入归一化 v1 JSON") { startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply { type = "*/*"; addCategory(Intent.CATEGORY_OPENABLE) }, 1) }
        button("扫描并手动选择目标") { scan() }
        button("上传并全部读回") {
            if (!ready || writing != null) { log("LOCAL_NOT_READY"); return@button }
            val value = score ?: run { log("先导入 JSON"); return@button }
            val sid = sessionNumber; sessionNumber = if (sid == 65535) 1 else sid + 1
            getPreferences(MODE_PRIVATE).edit().putInt("next_session",sessionNumber).apply()
            client.start(value, sid, SystemClock.elapsedRealtime())
        }
        button("取消（等待真实 ABORT 回复）") { client.cancel(SystemClock.elapsedRealtime()) }
        button("断开") { stop("LOCAL_DISCONNECT") }
        button("导出原字节日志") { startActivityForResult(Intent(Intent.ACTION_CREATE_DOCUMENT).apply { type = "text/plain"; putExtra(Intent.EXTRA_TITLE,"m3-score-log.txt") }, 2) }
        layout.addView(info); layout.addView(devices)
        setContentView(ScrollView(this).apply { addView(layout) }); handler.post(clock)
    }
    private fun permitted(): Boolean {
        val permissions = if (Build.VERSION.SDK_INT >= 31) arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT) else arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
        val missing = permissions.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) { requestPermissions(missing.toTypedArray(),3); log("需用户明确授予权限，拒绝后不扫描"); return false }
        return true
    }
    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode,permissions,grantResults)
        log(if (grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }) "权限已授予；请再次点扫描" else "LOCAL_PERMISSION_DENIED")
    }
    private fun scan() {
        if (!permitted()) return
        val bt = adapter ?: run { log("LOCAL_NO_BLE"); return }
        if (Protocol.scanGate(true,bt.isEnabled)!="OK") { log("LOCAL_BLUETOOTH_DISABLED：请用户在系统开启"); return }
        if (scanning) bt.bluetoothLeScanner.stopScan(scanCallback)
        seen.clear(); devices.removeAllViews(); scanning = true
        bt.bluetoothLeScanner.startScan(listOf(ScanFilter.Builder().setServiceUuid(ParcelUuid(UUID.fromString(Protocol.SERVICE))).build()),ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(),scanCallback)
        handler.postDelayed({ if (scanning) { bt.bluetoothLeScanner.stopScan(scanCallback); scanning=false; log("扫描结束") } },10000)
    }
    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) { handler.post {
            val address = result.device.address
            if (seen.size < 16 && seen.add(address)) devices.addView(Button(this@MainActivity).apply {
                text = "${result.scanRecord?.deviceName ?: "候选"} / $address / ${result.rssi} dBm"
                setOnClickListener {
                    adapter?.bluetoothLeScanner?.stopScan(this@MainActivity.scanCallback); scanning=false
                    stop("选择新目标 $address"); client=Protocol.Session(this@MainActivity)
                    selectedAddress=address
                    gatt=result.device.connectGatt(this@MainActivity,false,callbacks,BluetoothDevice.TRANSPORT_LE)
                }
            })
        } }
        override fun onScanFailed(errorCode: Int) { handler.post { scanning=false; log("LOCAL_SCAN_FAILED $errorCode") } }
    }
    private val callbacks = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) { handler.post {
            if (g !== gatt || !Protocol.selectedTarget(selectedAddress,g.device.address)) return@post
            if (status != BluetoothGatt.GATT_SUCCESS || newState == BluetoothProfile.STATE_DISCONNECTED) stop("LOCAL_DISCONNECT $status")
            else if (newState == BluetoothProfile.STATE_CONNECTED && !g.discoverServices()) stop("LOCAL_DISCOVER_REJECT")
        } }
        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) { handler.post {
            if (g !== gatt) return@post
            if (status != BluetoothGatt.GATT_SUCCESS) { stop("LOCAL_SERVICE_ERROR"); return@post }
            val service=g.getService(UUID.fromString(Protocol.SERVICE))
            rx=service?.getCharacteristic(UUID.fromString(Protocol.RX))
            val tx=service?.getCharacteristic(UUID.fromString(Protocol.TX))
            if (rx == null || tx == null || !g.setCharacteristicNotification(tx,true)) { stop("LOCAL_UUID_ERROR"); return@post }
            val descriptor=tx.getDescriptor(cccd)
            if (descriptor == null) { stop("LOCAL_CCCD_MISSING"); return@post }
            descriptor.value=BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
            if (!g.writeDescriptor(descriptor)) stop("LOCAL_CCCD_REJECT")
        } }
        override fun onDescriptorWrite(g: BluetoothGatt, d: BluetoothGattDescriptor, status: Int) { handler.post {
            if (g !== gatt) return@post
            if (status != BluetoothGatt.GATT_SUCCESS) { stop("LOCAL_CCCD_FAILED"); return@post }
            if (d.characteristic.uuid == UUID.fromString(Protocol.TX)) {
                val local=g.getService(UUID.fromString(Protocol.SERVICE))?.getCharacteristic(UUID.fromString(Protocol.LOCAL))
                val descriptor=local?.getDescriptor(cccd)
                if (local == null || descriptor == null || !g.setCharacteristicNotification(local,true)) { stop("LOCAL_STATUS_MISSING"); return@post }
                descriptor.value=BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                if (!g.writeDescriptor(descriptor)) stop("LOCAL_STATUS_REJECT")
            } else { ready=true; log("GATT就绪；尚未收到任何FPGA应用ACK") }
        } }
        override fun onCharacteristicWrite(g: BluetoothGatt, ch: BluetoothGattCharacteristic, status: Int) { handler.post {
            if (g !== gatt || writing == null) return@post
            if (status != BluetoothGatt.GATT_SUCCESS) { stop("LOCAL_WRITE_FAILED"); return@post }
            offset+=minOf(20,writing!!.size-offset)
            if (offset==writing!!.size) { log("TX ${Protocol.hex(writing!!)}"); writing=null; client.transportWritten(); nextFrame() } else writeFragment()
        } }
        override fun onCharacteristicChanged(g: BluetoothGatt, ch: BluetoothGattCharacteristic) {
            val raw=ch.value.copyOf(); val uuid=ch.uuid
            handler.post {
                if (g !== gatt) return@post
                if (uuid == UUID.fromString(Protocol.TX)) { log("RX ${Protocol.hex(raw)}"); client.notify(raw,SystemClock.elapsedRealtime()) }
                else if (uuid == UUID.fromString(Protocol.LOCAL)) { log("BRIDGE_LOCAL ${Protocol.hex(raw)}"); if (raw.size != 6 || raw[0].toInt()!=1 || raw[1].toInt()!=0) stop("LOCAL_BRIDGE_ERROR") }
            }
        }
    }
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode,resultCode,data)
        if (resultCode != RESULT_OK || data?.data == null) return
        try {
            if (requestCode == 1) {
                val bytes=contentResolver.openInputStream(data.data!!)?.use { input ->
                    val output=java.io.ByteArrayOutputStream()
                    val part=ByteArray(4096)
                    while (output.size()<=262144) {
                        val n=input.read(part,0,minOf(part.size,262145-output.size()))
                        if (n<0) break
                        output.write(part,0,n)
                    }
                    output.toByteArray()
                } ?: error("import stream")
                require(bytes.size<=262144) { "JSON too large" }
                score=Protocol.score(String(bytes,Charsets.UTF_8)); log("导入 ${score!!.records.size/8} 项，不开始播放")
            } else if (requestCode == 2) contentResolver.openOutputStream(data.data!!)?.use { it.write(rawLog.toString().toByteArray(Charsets.UTF_8)) }
        } catch (e: Exception) { log("LOCAL_JSON_OR_IO ${e.message}") }
    }
    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        try { if (scanning) adapter?.bluetoothLeScanner?.stopScan(scanCallback); stop("LOCAL_ACTIVITY_DESTROY") } catch (_: SecurityException) { }
        super.onDestroy()
    }
}
