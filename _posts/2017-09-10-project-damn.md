---
layout: post
title: "Denton Air Quality and The Monitoring Thereof"
summary: A proposal for universal environmental monitoring systems
author: Dan Minshew
author_url: https://google.com
---

# Overview
It is often cited that Denton has some of the worst air quality in Texas, and as a city consistently scores below attainment[](#fn-1){: rel="footnote" id="ref-1" } thresholds for the region. At the same time, the ability to capture reliable data is limited and its storage and interpretation locked within academic or proprietary warehouses, and access placed at a premium.

Further, there is only a single air monitoring station[](#fn-2){: rel="footnote" id="ref-2" } within the city limits, which has been operational since 1998 and is maintained by TCEQ, with the nearest nodes present in Northlake and Pilot Point, respectively. It should be noted that there are no stations due north of the city, and the next northern-spanning station after Pilot Point is 117 miles from Denton, in the opposite direction. This points to a lack of open, strategic and thorough collection points within North Texas.

The near-obsession with data-driven decision making that is so crucial to modern business seems to somehow escape more modest civic applications, though a smart implementation of similar models might help drive commercial and political decisions at smaller scales, with mutual benefit.
Taking queues from modern Software-driven businesses and data-gathering practices, a system which emphasizes things like scalability, modularity, and usability could have a substantial impact on civic health, local business strategies and public policy. This document intends to outline some of those techniques and sketch a structure that maximizes the accessibility of comprehensive, quality data.

---

# Goals
### 1. Offer a single-source-of-truth for collected data which is safe and secure.
### 2. Provide guidance for amatuer or DIY groups to add nodes to the network.
### 3. Offer real-time statistics for environmental conditions across the Denton area.
### 4. Make the data publicly available.

---


# Specifications
- Particular focus domains should include, but might not be limited to--
- Cloud-based relational database capable of scaling with zero down-time.
- Modeling of data in a time series format.
- An open API that collects and retrieves network traffic.
- Automatic throttling of requests.
- Wi-fi or 3G capable Microcontrollers that can act as network nodes.
- Drivers for particular sensors to interface with MC’s.
- A deployment environment that supports continuous integration and migrations.
- Web-based “homepage” where anyone can view and interpolate datasets.
- Human-readable graphs to help provide intelligent data analytics.
- Documentation and instruction on the various parts of the project.
- Open-source practices, with all code available for review and contribution by the team, or anyone else in the OSS community.

<br />
# Additional Concerns / Flexibility In Architecture
Duis autem vel eum iriure dolor in hendrerit in vulputate velit esse molestie consequat, vel illum dolore eu feugiat nulla facilisis at vero eros et accumsan.
Duis autem vel eum iriure dolor in hendrerit in vulputate velit esse molestie consequat, vel illum dolore eu feugiat nulla facilisis at vero eros et accumsan.

<br />
# Milestones
These tasks are predominantly asynchronous, and should be able to built more or less concurrently given that data models are agreed upon beforehand.

### - Air Quality API
A RESTful service that consumes and serves environment data.

### - Persistent Database
Schema should be built with scalability and dynamism of data models in mind.

### - MVP Hardware Integration
A Raspberry Pi (or similar) microcontroller with network connectivity and data transmission enabled.

### - “Better” Hardware Integration
After buy-in from community and/or local businesses, upgrades to hardware, enclosures and sensors can begin rolling out.

---

# Conclusion
The project should value the lessons of LEAN[](#fn-3){: rel="footnote" id="ref-3" } software development, and focus on preventing lock-in with particular protocols or architectures. As long as a node can communicate reliable environmental data, the database should be capable of storing that information and retrieving it in a consistent fashion that’s optimized for efficiency and consumability.

An open license should be preferred, and open-source practices preferred in almost all instances, promoting the larger movement of open government data[](#fn-4){: rel="footnote" id="ref-4" } and smart cities[](#fn-5){: rel="footnote" id="ref-5" }. Additionally, the practice of clearly communicating intents and goals should be made paramount, and the experience of onboarding a new user, or new node onto the network, should be as streamlined and stress-free as possible.

While many projects in the past[](#fn-6){: rel="footnote" id="ref-6" } have tackled this problem, few have seen wide adoption. What can emerge from any amount of progress made in this space will be the creation of a set of Best Practices, that can influence future projects and hopefully increase the need for more tech-enabled, data-conscious citizens.

---

<ol>
  <li id="fn-1">
    <a href="http://www.airnorthtexas.org/airquality">
      North Texas Air Quality (map of nonattainment areas)
    </a>.

    Retrieved Sept 10, 2017.

    <a href="#ref-1" rel="footnote-return"></a>
  </li>

  <li id="fn-2">
    <a href="https://www.tceq.texas.gov/cgi-bin/compliance/monops/daily_summary.pl?cams=56">
      Denton Airport South C56/A163/X157 (data by site, by data -- all parameters)
    </a>.

    Retrieved Sept 10, 2017.

    <a href="#ref-2" rel="footnote-return"></a>
  </li>

  <li id="fn-3">
    <a href="https://en.wikipedia.org/wiki/Lean_software_development">
      Lean Software Development (wikipedia)
    </a>.

    Retrieved Sept 10, 2017.

    <a href="#ref-3" rel="footnote-return"></a>
  </li>

  <li id="fn-4">
    <a href="https://www.data.gov/open-gov">
      Open Government (data.gov/open-gov)
    </a>.

    Retrieved Sept 10, 2017.

    <a href="#ref-4" rel="footnote-return"></a>
  </li>

  <li id="fn-5">
    <a href="https://en.wikipedia.org/wiki/Smart_city">
      Smart City (wikipedia)
    </a>.

    Retrieved Sept 10, 2017.

    <a href="#ref-5" rel="footnote-return"></a>
  </li>

  <li id="fn-6">
    <a href="http://airpi.es/">
      Airpi.es
    </a>.

    Retrieved Sept 10, 2017.

    <a href="#ref-6" rel="footnote-return"></a>
  </li>

</ol>
