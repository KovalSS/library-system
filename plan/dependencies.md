# Схема залежностей між тікетами

Жовтий — Gate, зелений — Test, синій — Feature, фіолетовий — Verification, червоний — Validation, сірий — Documentation, помаранчевий — Addendum. Показано скорочений граф (транзитивні зв'язки опущено).

```mermaid
flowchart TD
    subgraph S0["Етап 0"]
        LS40["LS-40<br/>Add"]
        LS01["LS-01<br/>GATE"]
    end
    subgraph S1["Етап 1"]
        LS02["LS-02<br/>Doc"]
    end
    subgraph S2["Етап 2 Ядро"]
        LS03["LS-03<br/>Test"]
        LS04["LS-04<br/>Test"]
        LS05["LS-05<br/>Test"]
        LS06["LS-06<br/>Test"]
        LS07["LS-07<br/>Test"]
        LS08["LS-08<br/>GATE"]
        LS09["LS-09<br/>Feat"]
        LS10["LS-10<br/>Feat"]
        LS11["LS-11<br/>Feat"]
        LS12["LS-12<br/>Feat"]
        LS13["LS-13<br/>Feat"]
        LS14["LS-14<br/>Verif"]
    end
    subgraph S3["Етап 3 Видача, бронювання, штрафи"]
        LS15["LS-15<br/>Test"]
        LS16["LS-16<br/>Test"]
        LS17["LS-17<br/>Test"]
        LS18["LS-18<br/>GATE"]
        LS19["LS-19<br/>Feat"]
        LS20["LS-20<br/>Feat"]
        LS21["LS-21<br/>Feat"]
        LS22["LS-22<br/>Verif"]
        LS23["LS-23<br/>GATE"]
    end
    subgraph S4["Етап 4"]
        LS24["LS-24<br/>Test"]
        LS25["LS-25<br/>Test"]
        LS26["LS-26<br/>Test"]
        LS27["LS-27<br/>Test"]
        LS28["LS-28<br/>Test"]
        LS29["LS-29<br/>GATE"]
        LS30["LS-30<br/>Feat"]
        LS31["LS-31<br/>Feat"]
        LS32["LS-32<br/>Feat"]
        LS33["LS-33<br/>Feat"]
        LS34["LS-34<br/>Feat"]
        LS35["LS-35<br/>Verif"]
    end
    subgraph S5["Етап 5"]
        LS36["LS-36<br/>Verif"]
        LS37["LS-37<br/>Valid"]
        LS38["LS-38<br/>Doc"]
        LS39["LS-39<br/>GATE"]
    end
    LS01 --> LS02
    LS02 --> LS03
    LS02 --> LS04
    LS02 --> LS05
    LS02 --> LS06
    LS02 --> LS07
    LS03 --> LS08
    LS04 --> LS08
    LS05 --> LS08
    LS06 --> LS08
    LS07 --> LS08
    LS08 --> LS09
    LS08 --> LS10
    LS08 --> LS11
    LS08 --> LS12
    LS08 --> LS13
    LS09 --> LS14
    LS10 --> LS14
    LS11 --> LS14
    LS12 --> LS14
    LS13 --> LS14
    LS14 --> LS15
    LS40 --> LS15
    LS14 --> LS16
    LS14 --> LS17
    LS15 --> LS18
    LS16 --> LS18
    LS17 --> LS18
    LS18 --> LS19
    LS19 --> LS20
    LS19 --> LS21
    LS20 --> LS22
    LS21 --> LS22
    LS22 --> LS23
    LS14 --> LS24
    LS14 --> LS25
    LS14 --> LS26
    LS14 --> LS27
    LS14 --> LS28
    LS24 --> LS29
    LS25 --> LS29
    LS26 --> LS29
    LS27 --> LS29
    LS28 --> LS29
    LS29 --> LS30
    LS29 --> LS31
    LS23 --> LS31
    LS29 --> LS32
    LS23 --> LS32
    LS29 --> LS33
    LS23 --> LS33
    LS29 --> LS34
    LS23 --> LS34
    LS30 --> LS35
    LS31 --> LS35
    LS32 --> LS35
    LS33 --> LS35
    LS34 --> LS35
    LS35 --> LS36
    LS36 --> LS37
    LS36 --> LS38
    LS37 --> LS39
    LS38 --> LS39
    style LS01 fill:#ffe9a3,stroke:#555,color:#111
    style LS40 fill:#ffd7a8,stroke:#555,color:#111
    style LS02 fill:#e5e7eb,stroke:#555,color:#111
    style LS03 fill:#b8e6b8,stroke:#555,color:#111
    style LS04 fill:#b8e6b8,stroke:#555,color:#111
    style LS05 fill:#b8e6b8,stroke:#555,color:#111
    style LS06 fill:#b8e6b8,stroke:#555,color:#111
    style LS07 fill:#b8e6b8,stroke:#555,color:#111
    style LS08 fill:#ffe9a3,stroke:#555,color:#111
    style LS09 fill:#bcd6f7,stroke:#555,color:#111
    style LS10 fill:#bcd6f7,stroke:#555,color:#111
    style LS11 fill:#bcd6f7,stroke:#555,color:#111
    style LS12 fill:#bcd6f7,stroke:#555,color:#111
    style LS13 fill:#bcd6f7,stroke:#555,color:#111
    style LS14 fill:#e5d4f5,stroke:#555,color:#111
    style LS15 fill:#b8e6b8,stroke:#555,color:#111
    style LS16 fill:#b8e6b8,stroke:#555,color:#111
    style LS17 fill:#b8e6b8,stroke:#555,color:#111
    style LS18 fill:#ffe9a3,stroke:#555,color:#111
    style LS19 fill:#bcd6f7,stroke:#555,color:#111
    style LS20 fill:#bcd6f7,stroke:#555,color:#111
    style LS21 fill:#bcd6f7,stroke:#555,color:#111
    style LS22 fill:#e5d4f5,stroke:#555,color:#111
    style LS23 fill:#ffe9a3,stroke:#555,color:#111
    style LS24 fill:#b8e6b8,stroke:#555,color:#111
    style LS25 fill:#b8e6b8,stroke:#555,color:#111
    style LS26 fill:#b8e6b8,stroke:#555,color:#111
    style LS27 fill:#b8e6b8,stroke:#555,color:#111
    style LS28 fill:#b8e6b8,stroke:#555,color:#111
    style LS29 fill:#ffe9a3,stroke:#555,color:#111
    style LS30 fill:#bcd6f7,stroke:#555,color:#111
    style LS31 fill:#bcd6f7,stroke:#555,color:#111
    style LS32 fill:#bcd6f7,stroke:#555,color:#111
    style LS33 fill:#bcd6f7,stroke:#555,color:#111
    style LS34 fill:#bcd6f7,stroke:#555,color:#111
    style LS35 fill:#e5d4f5,stroke:#555,color:#111
    style LS36 fill:#e5d4f5,stroke:#555,color:#111
    style LS37 fill:#f8c4c4,stroke:#555,color:#111
    style LS38 fill:#e5e7eb,stroke:#555,color:#111
    style LS39 fill:#ffe9a3,stroke:#555,color:#111
```
