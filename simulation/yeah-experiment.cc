// YeAH-TCP NPE: configurable four-node wired testbed for ns-3.44.
// Uses the unmodified ns-3 congestion control implementations.
#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/traffic-control-module.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>

using namespace ns3;

namespace {
struct Flow {
    Ptr<PacketSink> sink;
    uint32_t cwnd = 0;
    uint32_t ssthresh = 0;
    double rttMs = 0;
    uint64_t cwndEvents = 0;
    uint64_t rttEvents = 0;
    double minRttMs = std::numeric_limits<double>::infinity();
};
std::array<Flow, 2> flows;
Ptr<Queue<Packet>> bottleneckQueue;
std::ofstream series;
Time startTime, endTime;
uint64_t queueSum = 0, queueSamples = 0, queueMax = 0;
uint64_t accepted = 0, overflow = 0, otherDrops = 0, randomDrops = 0;
uint64_t wireBytes = 0, wirePackets = 0, maxWirePacket = 0;

void Cwnd(uint32_t i, uint32_t, uint32_t value) {
    flows[i].cwnd = value;
    ++flows[i].cwndEvents;
}
void SsThresh(uint32_t i, uint32_t, uint32_t value) { flows[i].ssthresh = value; }
void Rtt(uint32_t i, Time, Time value) {
    if (value.IsPositive()) {
        auto &f = flows[i];
        f.rttMs = value.GetSeconds() * 1000.0;
        f.minRttMs = std::min(f.minRttMs, f.rttMs);
        ++f.rttEvents;
    }
}
void Attach(uint32_t i, Ptr<BulkSendApplication> app) {
    auto socket = app->GetSocket();
    NS_ABORT_MSG_IF(!socket, "BulkSend socket missing");
    NS_ABORT_MSG_UNLESS(socket->TraceConnectWithoutContext("CongestionWindow", MakeBoundCallback(&Cwnd, i)), "No cwnd trace");
    NS_ABORT_MSG_UNLESS(socket->TraceConnectWithoutContext("SlowStartThreshold", MakeBoundCallback(&SsThresh, i)), "No ssthresh trace");
    NS_ABORT_MSG_UNLESS(socket->TraceConnectWithoutContext("RTT", MakeBoundCallback(&Rtt, i)), "No RTT trace");
}
void Enqueued(Ptr<const Packet>) { ++accepted; }
void Overflow(Ptr<const Packet>) { ++overflow; }
void OtherDrop(Ptr<const Packet>) { ++otherDrops; }
void RandomDrop(Ptr<const Packet>) { ++randomDrops; }
void WireTx(Ptr<const Packet> p) {
    if (Simulator::Now() >= startTime && Simulator::Now() < endTime) {
        wireBytes += p->GetSize();
        ++wirePackets;
        maxWirePacket = std::max(maxWirePacket, static_cast<uint64_t>(p->GetSize()));
    }
}
uint64_t Rx(uint32_t i) { return flows[i].sink ? flows[i].sink->GetTotalRx() : 0; }
void Sample() {
    uint64_t q = bottleneckQueue->GetNPackets();
    if (Simulator::Now() < endTime) {
        queueSum += q;
        ++queueSamples;
        queueMax = std::max(queueMax, q);
    }
    series << (Simulator::Now() - startTime).GetSeconds() << ',' << q << ','
           << Rx(0) << ',' << Rx(1) << ',' << flows[0].cwnd << ',' << flows[1].cwnd << ','
           << flows[0].ssthresh << ',' << flows[1].ssthresh << ',' << flows[0].rttMs << ','
           << flows[1].rttMs << ',' << wireBytes << ',' << overflow << ',' << otherDrops << ','
           << randomDrops << '\n';
    if (Simulator::Now() < endTime) {
        Simulator::Schedule(std::min(MilliSeconds(10), endTime - Simulator::Now()), &Sample);
    }
}
std::string TcpName(std::string s) {
    if (s == "yeah") return "ns3::TcpYeah";
    if (s == "reno") return "ns3::TcpNewReno";
    if (s == "cubic") return "ns3::TcpCubic";
    if (s == "htcp") return "ns3::TcpHtcp";
    if (s == "highspeed") return "ns3::TcpHighSpeed";
    NS_ABORT_MSG("Unknown TCP name: " << s);
    return "";
}
void SelectTcp(Ptr<Node> node, const std::string& name) {
    auto tcp = node->GetObject<TcpL4Protocol>();
    tcp->SetAttribute("SocketType", TypeIdValue(TypeId::LookupByName(TcpName(name))));
    TypeIdValue actual;
    tcp->GetAttribute("SocketType", actual);
    std::cout << "Node " << node->GetId() << " SocketType=" << actual.Get().GetName() << '\n';
}
Ptr<PointToPointNetDevice> Device(const NetDeviceContainer& c, uint32_t i) {
    auto d = DynamicCast<PointToPointNetDevice>(c.Get(i));
    NS_ABORT_MSG_IF(!d, "Unexpected device type");
    return d;
}
} // namespace

int main(int argc, char* argv[]) {
    std::string tcp1 = "yeah", tcp2 = "yeah", out = "yeah-output";
    double mbps = 50, rtt1 = 80, rtt2 = 80, ratio = 1, duration = 20, loss = 0;
    double flow2Start = 0, flow2Stop = -1;
    uint32_t seed = 1, run = 1, nFlows = 2, mss = 1448, initialCwnd = 10, initialSsthreshSegments = 0;
    CommandLine cmd(__FILE__);
    cmd.AddValue("tcp1", "yeah, reno, cubic, htcp, highspeed", tcp1);
    cmd.AddValue("tcp2", "Algorithm for second sender", tcp2);
    cmd.AddValue("flows", "Number of flows (1 or 2)", nFlows);
    cmd.AddValue("capacity", "Bottleneck Mbps", mbps);
    cmd.AddValue("rtt1", "Nominal propagation RTT for sender 1 (ms)", rtt1);
    cmd.AddValue("rtt2", "Nominal propagation RTT for sender 2 (ms)", rtt2);
    cmd.AddValue("bufferRatio", "Buffer / nominal BDP", ratio);
    cmd.AddValue("duration", "Measurement duration in seconds", duration);
    cmd.AddValue("loss", "Independent forward packet error probability", loss);
    cmd.AddValue("flow2Start", "Second application start relative to measurement start (s)", flow2Start);
    cmd.AddValue("flow2Stop", "Second application stop relative to start (-1 = end); queued TCP data can drain", flow2Stop);
    cmd.AddValue("seed", "RNG seed", seed);
    cmd.AddValue("run", "RNG run", run);
    cmd.AddValue("mss", "TCP payload bytes (1448 for IPv4 TCP timestamps)", mss);
    cmd.AddValue("initialCwnd", "Initial congestion window in segments", initialCwnd);
    cmd.AddValue("initialSsthreshSegments", "Initial ssthresh segments; 0 = UINT32_MAX", initialSsthreshSegments);
    cmd.AddValue("out", "Output directory", out);
    cmd.Parse(argc, argv);
    if (flow2Stop < 0) flow2Stop = duration;
    NS_ABORT_MSG_IF(nFlows < 1 || nFlows > 2 || mbps <= 0 || mbps >= 1000 || rtt1 <= 2 || rtt2 <= 2 || ratio <= 0 || duration <= 0 || loss < 0 || loss > 1 || mss == 0 || mss > 1448 || initialCwnd == 0 || (nFlows == 2 && (flow2Start < 0 || flow2Stop <= flow2Start || flow2Stop > duration)), "Invalid scenario parameters");
    RngSeedManager::SetSeed(seed);
    RngSeedManager::SetRun(run);
    const uint64_t bps = static_cast<uint64_t>(std::llround(mbps * 1e6));
    const double minRtt = nFlows == 2 ? std::min(rtt1, rtt2) : rtt1;
    const double bdpPackets = bps * minRtt / 1000.0 / (8.0 * 1500.0);
    const uint32_t buffer = std::max(1U, static_cast<uint32_t>(std::floor(bdpPackets * ratio)));
    // Fixed large buffers; 64 MiB exceeds BDP even at 500 Mbps and 480 ms.
    Config::SetDefault("ns3::TcpSocket::SndBufSize", UintegerValue(64 * 1024 * 1024));
    Config::SetDefault("ns3::TcpSocket::RcvBufSize", UintegerValue(64 * 1024 * 1024));
    Config::SetDefault("ns3::TcpSocket::SegmentSize", UintegerValue(mss));
    Config::SetDefault("ns3::TcpSocket::InitialCwnd", UintegerValue(initialCwnd));
    Config::SetDefault("ns3::TcpSocket::InitialSlowStartThreshold", UintegerValue(initialSsthreshSegments ? initialSsthreshSegments * mss : std::numeric_limits<uint32_t>::max()));
    Config::SetDefault("ns3::TcpSocketBase::WindowScaling", BooleanValue(true));
    Config::SetDefault("ns3::TcpSocketBase::Timestamp", BooleanValue(true));
    Config::SetDefault("ns3::TcpSocketBase::Sack", BooleanValue(true));
    Config::SetDefault("ns3::TcpSocket::DelAckCount", UintegerValue(2));

    NodeContainer nodes;
    nodes.Create(4); // 0,1 senders; 2 router; 3 receiver
    InternetStackHelper internet;
    internet.Install(nodes);
    SelectTcp(nodes.Get(0), tcp1);
    if (nFlows == 2) SelectTcp(nodes.Get(1), tcp2);
    // Exactly one physical FIFO queue per interface; no hidden root qdisc.
    PointToPointHelper access;
    access.DisableFlowControl();
    access.SetDeviceAttribute("DataRate", StringValue("1Gbps"));
    access.SetDeviceAttribute("Mtu", UintegerValue(1500));
    access.SetQueue("ns3::DropTailQueue", "MaxSize", StringValue("20000p"));
    // Shared bottleneck has 1 ms one-way propagation; allocate the rest to access.
    access.SetChannelAttribute("Delay", TimeValue(Seconds((rtt1 / 2 - 1) / 1000.0)));
    auto a = access.Install(nodes.Get(0), nodes.Get(2));
    access.SetChannelAttribute("Delay", TimeValue(Seconds((rtt2 / 2 - 1) / 1000.0)));
    auto b = access.Install(nodes.Get(1), nodes.Get(2));
    PointToPointHelper bottleneck;
    bottleneck.DisableFlowControl();
    bottleneck.SetDeviceAttribute("DataRate", DataRateValue(DataRate(bps)));
    bottleneck.SetDeviceAttribute("Mtu", UintegerValue(1500));
    bottleneck.SetChannelAttribute("Delay", TimeValue(MilliSeconds(1)));
    bottleneck.SetQueue("ns3::DropTailQueue", "MaxSize", StringValue(std::to_string(buffer) + "p"));
    auto c = bottleneck.Install(nodes.Get(2), nodes.Get(3));
    Ipv4AddressHelper ip;
    ip.SetBase("10.1.1.0", "255.255.255.0"); ip.Assign(a);
    ip.SetBase("10.1.2.0", "255.255.255.0"); ip.Assign(b);
    ip.SetBase("10.1.3.0", "255.255.255.0"); auto ci = ip.Assign(c);
    // Remove root queue discs only when installed.
    TrafficControlHelper tc;
    for (const auto& devices : {a, b, c})
    {
        for (uint32_t i = 0; i < devices.GetN(); ++i)
        {
            auto dev = devices.Get(i);
            auto layer = dev->GetNode()->GetObject<TrafficControlLayer>();
            if (layer && layer->GetRootQueueDiscOnDevice(dev))
            {
                tc.Uninstall(dev);
            }
        }
    }
    Ipv4GlobalRoutingHelper::PopulateRoutingTables();

    auto forward = Device(c, 0);
    auto receiver = Device(c, 1);
    bottleneckQueue = forward->GetQueue();
    NS_ABORT_MSG_UNLESS(bottleneckQueue->TraceConnectWithoutContext("Enqueue", MakeCallback(&Enqueued)), "No queue enqueue trace");
    NS_ABORT_MSG_UNLESS(bottleneckQueue->TraceConnectWithoutContext("Drop", MakeCallback(&Overflow)), "No queue drop trace");
    for (auto d : {Device(a, 0), Device(a, 1), Device(b, 0), Device(b, 1), receiver}) {
        NS_ABORT_MSG_UNLESS(d->GetQueue()->TraceConnectWithoutContext("Drop", MakeCallback(&OtherDrop)), "No other drop trace");
    }
    NS_ABORT_MSG_UNLESS(forward->TraceConnectWithoutContext("PhyTxBegin", MakeCallback(&WireTx)), "No PHY TX trace");
    NS_ABORT_MSG_UNLESS(receiver->TraceConnectWithoutContext("PhyRxDrop", MakeCallback(&RandomDrop)), "No PHY RX drop trace");
    if (loss > 0) {
        auto em = CreateObject<RateErrorModel>();
        em->SetAttribute("ErrorUnit", EnumValue(RateErrorModel::ERROR_UNIT_PACKET));
        em->SetAttribute("ErrorRate", DoubleValue(loss));
        em->AssignStreams(17);
        receiver->SetReceiveErrorModel(em);
    }

    startTime = Seconds(1); endTime = startTime + Seconds(duration);
    for (uint32_t i = 0; i < nFlows; ++i) {
        uint16_t port = 5000 + i;
        PacketSinkHelper sink("ns3::TcpSocketFactory", InetSocketAddress(Ipv4Address::GetAny(), port));
        auto sa = sink.Install(nodes.Get(3));
        sa.Start(Seconds(0));
        flows[i].sink = DynamicCast<PacketSink>(sa.Get(0));
        BulkSendHelper sender("ns3::TcpSocketFactory", InetSocketAddress(ci.GetAddress(1), port));
        sender.SetAttribute("MaxBytes", UintegerValue(0));
        sender.SetAttribute("SendSize", UintegerValue(mss));
        auto app = sender.Install(nodes.Get(i));
        Time on = startTime + Seconds(i == 0 ? 0 : flow2Start);
        Time off = startTime + Seconds(i == 0 ? duration : flow2Stop);
        app.Start(on); app.Stop(off);
        Simulator::Schedule(on + NanoSeconds(1), &Attach, i, DynamicCast<BulkSendApplication>(app.Get(0)));
    }
    std::filesystem::create_directories(out);
    series.open(out + "/timeseries.csv");
    NS_ABORT_MSG_UNLESS(series.good(), "Cannot open timeseries.csv");
    series << std::fixed << std::setprecision(9);
    series << "time_s,queue_packets,rx1_bytes,rx2_bytes,cwnd1_bytes,cwnd2_bytes,ssthresh1_bytes,ssthresh2_bytes,rtt1_ms,rtt2_ms,wire_bytes,bottleneck_drops,other_drops,random_drops\n";
    std::cout << "Buffer=" << buffer << " packets; nominal BDP=" << bdpPackets << " packets; duration=" << duration << " s\n";
    Simulator::Schedule(startTime, &Sample);
    Simulator::Stop(endTime + NanoSeconds(1));
    Simulator::Run();
    series.close();

    const double gp1 = Rx(0) * 8.0 / duration / 1e6;
    const double gp2 = Rx(1) * 8.0 / duration / 1e6;
    const double goodput = gp1 + gp2;
    const double util = wireBytes * 8.0 / duration / bps;
    const double qMean = queueSamples ? static_cast<double>(queueSum) / queueSamples : 0;
    const double fairness = goodput > 0 ? goodput * goodput / (nFlows * (gp1 * gp1 + gp2 * gp2)) : 0;
    const double dropProb = accepted + overflow ? static_cast<double>(overflow) / (accepted + overflow) : 0;
    std::ofstream summary(out + "/summary.csv");
    NS_ABORT_MSG_UNLESS(summary.good(), "Cannot open summary.csv");
    summary << "tcp1,tcp2,flows,capacity_mbps,rtt1_target_ms,rtt2_target_ms,buffer_ratio,buffer_packets,bdp_packets,duration_s,loss_probability,seed,run,mss_bytes,initial_cwnd_segments,initial_ssthresh_segments,flow2_start_s,flow2_stop_s,rx1_bytes,rx2_bytes,goodput1_mbps,goodput2_mbps,total_goodput_mbps,goodput_over_capacity,wire_utilization,queue_mean_packets,queue_normalized,queue_max_sampled,queue_samples,queue_enqueued,bottleneck_drops,overflow_probability,other_drops,random_drops,wire_packets,max_wire_packet_bytes,jain_index,cwnd1_events,cwnd2_events,rtt1_events,rtt2_events,min_rtt1_ms,min_rtt2_ms\n";
    summary << std::fixed << std::setprecision(10) << tcp1 << ',' << tcp2 << ',' << nFlows << ',' << mbps << ',' << rtt1 << ',' << rtt2 << ',' << ratio << ',' << buffer << ',' << bdpPackets << ',' << duration << ',' << loss << ',' << seed << ',' << run << ',' << mss << ',' << initialCwnd << ',' << initialSsthreshSegments << ',' << flow2Start << ',' << flow2Stop << ',' << Rx(0) << ',' << Rx(1) << ',' << gp1 << ',' << gp2 << ',' << goodput << ',' << goodput / mbps << ',' << util << ',' << qMean << ',' << qMean / buffer << ',' << queueMax << ',' << queueSamples << ',' << accepted << ',' << overflow << ',' << dropProb << ',' << otherDrops << ',' << randomDrops << ',' << wirePackets << ',' << maxWirePacket << ',' << fairness << ',' << flows[0].cwndEvents << ',' << flows[1].cwndEvents << ',' << flows[0].rttEvents << ',' << flows[1].rttEvents << ',' << flows[0].minRttMs << ',' << flows[1].minRttMs << '\n';
    summary.close();
    std::cout << std::fixed << std::setprecision(4) << "Goodput1=" << gp1 << " Mbps, Goodput2=" << gp2 << " Mbps, wire utilization=" << util << ", queue mean=" << qMean << ", drops=" << overflow << ", other drops=" << otherDrops << ", random drops=" << randomDrops << '\n';
    std::cout << "Saved " << out << "/summary.csv and timeseries.csv\n";
    Simulator::Destroy();
    return 0;
}
