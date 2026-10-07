package org.m3.score;
import java.util.*;
import java.io.ByteArrayOutputStream;

/** Pure Java public wire core; used by Android and the real desktop harness. */
public final class Protocol {
    public static final String SERVICE="761e0001-6ccd-4aa4-9e21-104647415031";
    public static final String RX="761e0002-6ccd-4aa4-9e21-104647415031";
    public static final String TX="761e0003-6ccd-4aa4-9e21-104647415031";
    public static final String LOCAL="761e0004-6ccd-4aa4-9e21-104647415031";
    public static String scanGate(boolean permission,boolean enabled) {
        return !permission?"LOCAL_PERMISSION_DENIED":(!enabled?"LOCAL_BLUETOOTH_DISABLED":"OK");
    }
    public static boolean selectedTarget(String selected,String reported) { return selected!=null && selected.equals(reported); }
    public static int u16(byte[] p,int i) { return (p[i]&255)|((p[i+1]&255)<<8); }
    public static long u32(byte[] p,int i) { return (u16(p,i)&65535L)|((long)u16(p,i+2)<<16); }
    public static void put(byte[] p,int i,long v,int n) { for(int k=0;k<n;k++) p[i+k]=(byte)(v>>>(8*k)); }
    public static int crc(byte[] p,int start,int n) {
        int c=65535;
        for(int i=start;i<start+n;i++) { c^=(p[i]&255)<<8; for(int k=0;k<8;k++) c=((c<<1)^((c&32768)!=0?0x1021:0))&65535; }
        return c;
    }
    public static byte[] frame(int cmd,int session,int seq,int offset,byte[] payload) {
        if(payload.length>128) throw new IllegalArgumentException("length");
        byte[] b=new byte[14+payload.length]; b[0]=(byte)165; b[1]=90; b[2]=1; b[3]=(byte)cmd;
        put(b,4,session,2); put(b,6,seq,2); put(b,8,offset,2); put(b,10,payload.length,2);
        System.arraycopy(payload,0,b,12,payload.length); put(b,b.length-2,crc(b,2,b.length-4),2); return b;
    }
    public static void validate(byte[] b) {
        if(b.length<14 || b.length>142 || (b[0]&255)!=165 || b[1]!=90 || b[2]!=1 || u16(b,10)>128 || b.length!=14+u16(b,10)) throw new IllegalArgumentException("FRAME_FORMAT");
        if(crc(b,2,b.length-4)!=u16(b,b.length-2)) throw new IllegalArgumentException("FRAME_CRC");
    }
    public static String hex(byte[] b) { StringBuilder s=new StringBuilder(); for(byte v:b) s.append(String.format(Locale.ROOT,"%02x",v&255)); return s.toString(); }
    public static byte[] unhex(String h) {
        if(h.length()%2!=0) throw new IllegalArgumentException("hex"); byte[] b=new byte[h.length()/2];
        for(int i=0;i<b.length;i++) b[i]=(byte)Integer.parseInt(h.substring(2*i,2*i+2),16); return b;
    }
    public static final class Score {
        public final long id; public final byte[] records;
        Score(long id,byte[] records) { this.id=id; this.records=records; }
    }
    private static long number(Object v,long max) { if(!(v instanceof Long) || (Long)v<0 || (Long)v>max) throw new IllegalArgumentException("integer range"); return (Long)v; }
    private static void keys(Map<?,?> m,String... keys) { if(!m.keySet().equals(new HashSet<String>(Arrays.asList(keys)))) throw new IllegalArgumentException("JSON fields"); }
    public static Score score(String json) {
        Object root=new Json(json).parse(); if(!(root instanceof Map)) throw new IllegalArgumentException("score object");
        Map<?,?> m=(Map<?,?>)root; keys(m,"schema","sample_hz","score_id","events");
        if(number(m.get("schema"),1)!=1 || number(m.get("sample_hz"),48000)!=48000) throw new IllegalArgumentException("schema/sample_hz");
        long id=number(m.get("score_id"),0xffffffffL); if(!(m.get("events") instanceof List)) throw new IllegalArgumentException("events");
        List<?> events=(List<?>)m.get("events"); if(events.isEmpty() || events.size()>512) throw new IllegalArgumentException("capacity");
        byte[] data=new byte[events.size()*8]; long prev=0; int i=0;
        for(Object e:events) {
            if(!(e instanceof Map)) throw new IllegalArgumentException("event"); Map<?,?> q=(Map<?,?>)e; keys(q,"tick","type","channel","note","velocity");
            long tick=number(q.get("tick"),0xffffffffL), ch=number(q.get("channel"),15), note=number(q.get("note"),127), vel=number(q.get("velocity"),127);
            Object type=q.get("type"); if(!"note_on".equals(type) && !"note_off".equals(type) || tick<prev) throw new IllegalArgumentException("order/type");
            put(data,i,tick,4); data[i+4]=(byte)("note_off".equals(type)||vel==0?1:0); data[i+5]=(byte)ch; data[i+6]=(byte)note; data[i+7]=(byte)vel;
            i+=8; prev=tick;
        }
        return new Score(id,data);
    }
    /** Strict bounded JSON, rejects duplicate fields/floats/bools as integers. */
    static final class Json {
        final String s; int i=0;
        Json(String s) { if(s.length()>262144) throw new IllegalArgumentException("JSON size"); this.s=s; }
        void ws() { while(i<s.length() && " \r\n\t".indexOf(s.charAt(i))>=0) i++; }
        char next() { if(i>=s.length()) throw new IllegalArgumentException("truncated JSON"); return s.charAt(i++); }
        void need(char c) { ws(); if(next()!=c) throw new IllegalArgumentException("JSON syntax"); }
        Object parse() { Object x=value(0); ws(); if(i!=s.length()) throw new IllegalArgumentException("JSON trailing"); return x; }
        String string() {
            need('"'); StringBuilder b=new StringBuilder();
            for(;;) { char c=next(); if(c=='"') return b.toString(); if(c<32) throw new IllegalArgumentException("JSON control");
                if(c=='\\') { c=next(); if(c=='u') { if(i+4>s.length()) throw new IllegalArgumentException("unicode"); c=(char)Integer.parseInt(s.substring(i,i+4),16); i+=4; }
                    else { int p="\"\\/bfnrt".indexOf(c); if(p<0) throw new IllegalArgumentException("escape"); c="\"\\/\b\f\n\r\t".charAt(p); } } b.append(c); }
        }
        Object value(int depth) {
            if(depth>8) throw new IllegalArgumentException("JSON depth"); ws(); if(i>=s.length()) throw new IllegalArgumentException("JSON empty"); char c=s.charAt(i);
            if(c=='"') return string();
            if(c=='{' || c=='[') {
                i++; ws(); boolean obj=c=='{'; char end=obj?'}':']'; Map<String,Object> map=new LinkedHashMap<>(); List<Object> list=new ArrayList<>();
                if(i<s.length() && s.charAt(i)==end) { i++; return obj?map:list; }
                for(;;) { if(obj) { String key=string(); need(':'); if(map.containsKey(key)) throw new IllegalArgumentException("duplicate field"); map.put(key,value(depth+1)); }
                    else list.add(value(depth+1)); if(list.size()>512 || map.size()>8) throw new IllegalArgumentException("JSON capacity");
                    ws(); char delim=next(); if(delim==end) return obj?map:list; if(delim!=',') throw new IllegalArgumentException("JSON delimiter"); }
            }
            int start=i; if(c=='-') i++; if(i>=s.length() || !Character.isDigit(s.charAt(i))) throw new IllegalArgumentException("JSON integer only");
            if(s.charAt(i)=='0') i++; else while(i<s.length() && s.charAt(i)>='0' && s.charAt(i)<='9') i++;
            return Long.valueOf(s.substring(start,i));
        }
    }
    public interface Sink { void send(byte[] raw); void state(String message); }
    /** Bounded single transaction. Only verified peer responses advance it. */
    public static final class Session {
        final Sink sink; final byte[] buffer=new byte[142]; int used=0,target=0;
        byte[] request; List<byte[]> upload; Score score; int session,stage,index,retries; long due,total,last; boolean active;
        public Session(Sink sink) { this.sink=sink; }
        public void start(Score score,int session,long now) {
            if(active || session<1 || session>65535) throw new IllegalArgumentException("BUSY/session");
            this.score=score; this.session=session; upload=new ArrayList<>(); byte[] begin=new byte[14];
            put(begin,0,score.id,4); put(begin,4,score.records.length/8,2); put(begin,6,score.records.length,2); put(begin,8,crc(score.records,0,score.records.length),2); put(begin,10,48000,4);
            upload.add(frame(1,session,0,0,begin)); int seq=1;
            for(int offset=0;offset<score.records.length;offset+=128) upload.add(frame(2,session,seq++,offset,Arrays.copyOfRange(score.records,offset,Math.min(offset+128,score.records.length))));
            upload.add(frame(3,session,seq,0,new byte[0]));
            active=true; stage=0; index=0; used=0; target=0; total=now+180000; issue(frame(4,session,0,0,new byte[0]),now);
        }
        void issue(byte[] raw,long now) { request=raw; retries=0; due=now+2000; sink.state("WAIT cmd="+(raw[3]&255)+" seq="+u16(raw,6)); sink.send(raw.clone()); }
        public void fail(String reason) { if(active) sink.state("FAIL "+reason); active=false; used=target=0; request=null; }
        public void disconnect() { fail("LOCAL_DISCONNECT"); }
        public void cancel(long now) { if(active) { stage=4; used=target=0; issue(frame(4,session,65535,0,new byte[0]),now); } }
        public void transportWritten() { sink.state("TRANSPORT_ONLY"); }
        public void tick(long now) {
            if(!active) return;
            if(now>=total) { fail("TOTAL_DEADLINE"); return; }
            if(used!=0 && now-last>=2000) { used=target=0; }
            if(now>=due) { if(retries==2) fail("ACK_DEADLINE"); else { retries++; used=target=0; due=now+2000; sink.state("RETRY "+retries); sink.send(request.clone()); } }
        }
        public void notify(byte[] bytes,long now) {
            if(!active) return; tick(now); if(!active) return;
            for(byte v:bytes) {
                last=now;
                if(used==0) { if((v&255)==165) buffer[used++]=v; continue; }
                if(used==1 && v!=90) { used=((v&255)==165)?1:0; continue; }
                buffer[used++]=v;
                if(used==12) { int n=u16(buffer,10); if(n>128) { fail("RESPONSE_LENGTH"); return; } target=14+n; }
                if(target!=0 && used==target) {
                    byte[] raw=Arrays.copyOf(buffer,used); used=target=0;
                    try { validate(raw); response(raw,now); } catch(IllegalArgumentException ex) { fail(ex.getMessage()); }
                    if(!active) return;
                }
            }
        }
        void response(byte[] b,long now) {
            if(u16(b,4)!=session || u16(b,6)!=u16(request,6) || u16(b,8)!=u16(request,8)) { sink.state("UNRELATED"); return; }
            int cmd=request[3]&255,len=u16(b,10),kind=b[3]&255;
            if((kind!=128 && kind!=129) || len!=12+(cmd==6 && kind==128?8:0) || (b[12]&255)!=cmd) throw new IllegalArgumentException("RESPONSE_SHAPE");
            if(kind==129 || b[13]!=0) { fail("FPGA_NACK "+(b[13]&255)); return; }
            if(stage==4) { active=false; sink.state("CANCELLED peer ABORT ACK"); return; }
            if(cmd==5 || cmd==6) {
                if(b[14]!=1 || u16(b,16)!=score.records.length/8 || u32(b,18)!=score.id) throw new IllegalArgumentException("COMMITTED_IDENTITY");
            }
            if(cmd==6) {
                if(!Arrays.equals(Arrays.copyOfRange(b,24,32),Arrays.copyOfRange(score.records,index*8,index*8+8))) throw new IllegalArgumentException("READBACK");
                index++; sink.state("READ "+index+"/"+score.records.length/8);
                if(index==score.records.length/8) { active=false; sink.state("PASS full readback "+index); return; }
            }
            if(stage==0) { stage=1; index=0; }
            if(stage==1) { if(index<upload.size()) { issue(upload.get(index++),now); return; } stage=2; issue(frame(5,session,0,0,new byte[0]),now); return; }
            if(stage==2) { stage=3; index=0; }
            issue(frame(6,session,index,index,new byte[0]),now);
        }
    }
}
