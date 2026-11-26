# Generated from authored correction_md only. No learner data.
# Every variant executes in an isolated local environment.

# L01-V92
local({
x <- c(4,NA,9,0)
selection <- x>3
masque <- !is.na(x) & (x>3)
stopifnot(typeof(selection)=="logical",length(selection)==4,
          identical(selection,c(TRUE,NA,TRUE,FALSE)),
          is.na(sum(selection)),sum(masque)==2,
          identical(x[masque],c(4,9)))
selection
x[masque]

cat("R_EXECUTION_PASS L01-V92\n")
})

# L01-V93
local({
x <- c(2,4,6,8)
court <- c(1,10)
automatique <- x+court
offset <- c(1,1,10,10)
stopifnot(typeof(x)=="double",length(court)!=length(x),
          length(offset)==length(x),
          identical(automatique,c(3,14,7,18)),
          identical(x+offset,c(3,5,16,18)))
x+offset

cat("R_EXECUTION_PASS L01-V93\n")
})

# L01-V94
local({
chemin <- tempfile(fileext=".csv")
writeLines(c("mode,duree","velo,8","bus,12","velo,NA","velo,10"),chemin)
d <- "ancien objet sans rapport"
importe <- read.csv(chemin)
garder <- !is.na(importe$mode) & importe$mode=="velo" & !is.na(importe$duree)
valeurs <- importe$duree[garder]
stopifnot(length(valeurs)>0)
etapes <- mean(valeurs)
pipeline <- valeurs |> mean()
stopifnot(etapes==9,pipeline==9,isTRUE(all.equal(etapes,pipeline)))
unlink(chemin)

cat("R_EXECUTION_PASS L01-V94\n")
})

# L02-V90
local({
y <- c(1,0,1,0,1,0)
score <- c(.9,.7,.4,.3,.6,.2)
p50 <- as.integer(score>.5); p75 <- as.integer(score>.75)
cm <- function(p) table(observation=factor(y,levels=0:1),
                        prediction=factor(p,levels=0:1))
cout <- function(p) sum(p==1 & y==0)+3*sum(p==0 & y==1)
cm(p50); cm(p75)
stopifnot(all(unname(cm(p50))==matrix(c(2,1,1,2),2)),
          all(unname(cm(p75))==matrix(c(3,2,0,1),2)),
          mean(p50==y)==4/6, mean(p75==y)==4/6,
          cout(p50)==4, cout(p75)==6)

cat("R_EXECUTION_PASS L02-V90\n")
})

# L02-V91
local({
y <- c(0,0,0,0,1,1); a <- rep(0L,6); b <- c(0L,0L,0L,1L,1L,1L)
t <- table(A=factor(a,levels=0:1),B=factor(b,levels=0:1))
stopifnot(all(unname(t)==matrix(c(3,0,3,0),2)),
          mean(a!=b)==.5, mean(a==y)==4/6, mean(b==y)==5/6)
t

cat("R_EXECUTION_PASS L02-V91\n")
})

# L03-V93
local({
u <- c(0,.5,.75); x <- -log1p(-u)/2
F_exp <- function(t,taux) ifelse(t<0,0,1-exp(-taux*t))
freq <- mean(x<=log(2)/2); theorie <- F_exp(log(2)/2,2)
stopifnot(F_exp(-1,2)==0, isTRUE(all.equal(freq,2/3)),
          isTRUE(all.equal(theorie,.5)),
          isTRUE(all.equal(x,c(0,log(2)/2,log(4)/2))))
c(frequence_grille=freq,probabilite=theorie)

cat("R_EXECUTION_PASS L03-V93\n")
})

# L04-V92
local({
x <- c(0,2,4); p <- c(.5,.25,.25)
m <- sum(p*x); v <- sum(p*(x-m)^2)
stopifnot(sum(p)==1,m==1.5,v==11/4,var(x)==4,
          isTRUE(all.equal(2/3*var(x),8/3)))
c(moyenne_loi=m,variance_loi=v,variance_R=var(x))

cat("R_EXECUTION_PASS L04-V92\n")
})

# L04-V93
local({
x <- c(0,2,4); xx <- rep(x,each=2)
vp <- function(z) mean((z-mean(z))^2)
stopifnot(isTRUE(all.equal(vp(x),8/3)),isTRUE(all.equal(vp(xx),8/3)),
          var(x)==4,isTRUE(all.equal(var(xx),16/5)))
c(variance_R_initiale=var(x),variance_R_dupliquee=var(xx))

cat("R_EXECUTION_PASS L04-V93\n")
})

# L05-V92
local({
pg <- pgeom(2,prob=.25,lower.tail=FALSE)
pn <- pnorm(-2,mean=1,sd=3)
stopifnot(isTRUE(all.equal(pg,27/64)),
          isTRUE(all.equal(pn,pnorm(-1))))
c(queue_geometrique=pg,queue_normale=pn)

cat("R_EXECUTION_PASS L05-V92\n")
})

# L05-V93
local({
k <- qgeom(.9,prob=.5); g <- k+1
F_rang <- function(j) pgeom(j-1,prob=.5)
stopifnot(k==3,g==4,F_rang(g-1)==7/8,F_rang(g)==15/16,
          F_rang(g-1)<.9,F_rang(g)>=.9)
g

cat("R_EXECUTION_PASS L05-V93\n")
})

# L06-V90
local({
set.seed(960)
x <- rexp(20,rate=2)
mauvais <- replicate(200,mean(x))
bon <- replicate(200,mean(rexp(20,rate=2)))
z <- sqrt(20)*(bon-.5)/.5
stopifnot(all(mauvais==mauvais[1]),var(mauvais)==0,
          length(bon)==200,all(is.finite(z)))
c(sd_theorique=1/(2*sqrt(20)),sd_observe=sd(bon),variance_z_observee=var(z))

cat("R_EXECUTION_PASS L06-V90\n")
})

# L06-V91
local({
x <- c(1,3,2,6); cumul <- cumsum(x)/seq_along(x)
set.seed(961)
repetitions <- replicate(3,mean(rexp(4,rate=2)))
stopifnot(identical(cumul,c(1,2,2,3)),length(repetitions)==3,
          all(is.finite(repetitions)))
cumul
repetitions

cat("R_EXECUTION_PASS L06-V91\n")
})

# L07-V90
local({
mc_a <- function(n) mean(runif(n))
mc_b <- function(n) mean((runif(n)+runif(n))/2)
set.seed(970)
a <- replicate(200,mc_a(1200))
b <- replicate(200,mc_b(600))
va <- 1/(12*1200); vb <- 1/(24*600)
stopifnot(isTRUE(all.equal(va,vb)),isTRUE(all.equal(sqrt(va),1/120)),
          length(a)==200,length(b)==200,
          all(is.finite(a)),all(is.finite(b)))
c(moyenne_A=mean(a),moyenne_B=mean(b),sd_A=sd(a),sd_B=sd(b),
  sd_theorique=1/120)

cat("R_EXECUTION_PASS L07-V90\n")
})

# L10-V92
local({
x <- c(5, 7, 9, 10, 14, 15)
set.seed(5)
mstar <- replicate(2000,
                   mean(sample(x, size=length(x), replace=TRUE)))
IC <- quantile(mstar, c(.025, .975))
IC
stopifnot(length(unique(mstar)) > 1, length(IC) == 2,
          IC[1] <= IC[2])

cat("R_EXECUTION_PASS L10-V92\n")
})

# L11-V92
local({
res <- binom.test(0, 25, p=.04, alternative="less")
res$p.value
stopifnot(abs(res$p.value - .96^25) < 1e-12)

cat("R_EXECUTION_PASS L11-V92\n")
})

# L12-V90
local({
id_avant <- c(1, 2, 3, 4)
avant <- c(10, 12, 13, 15)
id_apres <- c(3, 1, 4, 2)
apres <- c(12, 8, 14, 10)
ordre <- c(2, 4, 1, 3)
stopifnot(all(id_avant == id_apres[ordre]))
apres_aligne <- apres[ordre]
d_faux <- avant-apres
d <- avant-apres_aligne
c(moyenne_fausse=mean(d_faux), variance_fausse=var(d_faux),
  moyenne_correcte=mean(d), variance_correcte=var(d))
test <- t.test(avant, apres_aligne, paired=TRUE,
               alternative="two.sided", mu=0, conf.level=.95)
test
stopifnot(abs(mean(d)-1.5)<1e-12, abs(var(d)-1/3)<1e-12)

cat("R_EXECUTION_PASS L12-V90\n")
})

# L14-V90
local({
g <- c("A","A","A","A","B","B")
y <- c(0,2,4,6,10,14)
w <- prop.table(table(g))
m <- tapply(y,g,mean)
v <- tapply(y,g,function(z) mean((z-mean(z))^2))
intra <- sum(as.numeric(w)*v[names(w)])
inter <- sum(as.numeric(w)*(m[names(w)]-mean(y))^2)
total <- mean((y-mean(y))^2)
stopifnot(isTRUE(all.equal(unname(c(intra,inter,total)),c(14/3,18,68/3))))
stopifnot(isTRUE(all.equal(unname(intra+inter),total)))
print(c(intra=intra,inter=inter,total=total))

cat("R_EXECUTION_PASS L14-V90\n")
})

# L14-V91
local({
g <- c("A","A","A"); y <- c(1,2,3)
w <- prop.table(table(g))
m <- tapply(y,g,mean)
v <- tapply(y,g,function(z) mean((z-mean(z))^2))
intra <- sum(as.numeric(w)*v[names(w)])
inter <- sum(as.numeric(w)*(m[names(w)]-mean(y))^2)
total <- mean((y-mean(y))^2)
stopifnot(isTRUE(all.equal(unname(c(intra,inter,total)),c(2/3,0,2/3))))
print(c(intra=intra,inter=inter,total=total))

cat("R_EXECUTION_PASS L14-V91\n")
})

# L15-V90
local({
t_obs <- -2; ddl <- 8
p_direction <- pt(t_obs,df=ddl,lower.tail=FALSE)
p_bilateral <- 2*pt(-abs(t_obs),df=ddl)
p_F <- pf(t_obs^2,df1=1,df2=ddl,lower.tail=FALSE)
stopifnot(p_direction>.9,p_bilateral<.1)
stopifnot(isTRUE(all.equal(p_F,p_bilateral)))
print(c(p_direction=p_direction,p_bilateral=p_bilateral,p_F=p_F))

cat("R_EXECUTION_PASS L15-V90\n")
})
