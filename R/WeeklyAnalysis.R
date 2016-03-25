library("zoo", lib.loc="~/R/win-library/3.2")
library(forecast)
setwd("~/GitHub/SmartCity/R")
df = read.zoo(file="14_November12_Difference.csv", sep=",", header=TRUE, FUN=paste, FUN2=as.POSIXct)
dfseries = msts(df, seasonal.period=c(48,48*7), ts.frequency=48)
ds = dshw(dfseries, period1=48, period2=48*7)
plot(ds, xaxt="n")
# axis(side=1, at=c(0:50))

times <- time(df)
ticks <- seq(times[40], times[length(times)], by=48)
axis(1, at=ticks, labels=FALSE, tcl=-0.3)

# Print Hi-Res
pdf(file="DSHW_Plot.pdf", width = 18, height = 12)
plot(ds, xaxt="n", xlab="Date-Time", ylab="Entry-Exit Count Differential (centered at 200)")
dev.off()